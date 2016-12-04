from supervisor.options import UnhosedConfigParser
from supervisor.datatypes import list_of_strings
from supervisor.states import SupervisorStates
from supervisor.states import STOPPED_STATES
from supervisor.xmlrpc import Faults as SupervisorFaults
from supervisor.xmlrpc import RPCError
import supervisor.loggers
import json

API_VERSION = '1.0'

class Faults:
    NOT_IN_WHITELIST = 230

class GraceNamespaceRPCInterface:
    """ A supervisor rpc interface that facilitates manipulation of
    supervisor's configuration and state in ways that are not
    normally accessible at runtime.
    """
    def __init__(self, supervisord, whitelist=[]):
        self.supervisord = supervisord
        self._whitelist = list_of_strings(whitelist)

    def _update(self, func_name):
        self.update_text = func_name

        state = self.supervisord.get_state()
        if state == SupervisorStates.SHUTDOWN:
            raise RPCError(SupervisorFaults.SHUTDOWN_STATE)

        if len(self._whitelist):
            if func_name not in self._whitelist:
                raise RPCError(Faults.NOT_IN_WHITELIST, func_name)

    # RPC API methods

    def getAPIVersion(self):
        """ Return the version of the RPC API used by supervisor_twiddler

        @return int version version id
        """
        self._update('getAPIVersion')
        return API_VERSION

    def getGroupNames(self):
        """ Return an array with the names of the process groups.

        @return array                Process group names
        """
        self._update('getGroupNames')
        return list(self.supervisord.process_groups.keys())

    def log(self, message, level=supervisor.loggers.LevelsByName.INFO):
        """ Write an arbitrary message to the main supervisord log.  This is
            useful for recording information about your twiddling.

        @param  string      message      Message to write to the log
        @param  string|int  level        Log level name (INFO) or code (20)
        @return boolean                  Always True unless error
        """
        self._update('log')

        if isinstance(level, str):
            level = getattr(supervisor.loggers.LevelsByName,
                            level.upper(), None)

        if supervisor.loggers.LOG_LEVELS_BY_NUM.get(level, None) is None:
            raise RPCError(SupervisorFaults.INCORRECT_PARAMETERS)

        self.supervisord.options.logger.log(level, message)
        return True

    def addProgramToGroup(self, group_name, program_name, program_options):
        """ Add a new program to an existing process group.  Depending on the
            numprocs option, this will result in one or more processes being
            added to the group.

        @param string  group_name       Name of an existing process group
        @param string  program_name     Name of the new process in the process table
        @param struct  program_options  Program options, same as in supervisord.conf
        @return boolean                 Always True unless error
        """
        self._update('addProgramToGroup')

        group = self._getProcessGroup(group_name)

        # make configparser instance for program options
        section_name = 'program:%s' % program_name
        parser = self._makeConfigParser(section_name, program_options)

        # make process configs from parser instance
        options = self.supervisord.options
        try:
            new_configs = options.processes_from_section(parser, section_name, group_name)
        except ValueError as e:
            raise RPCError(SupervisorFaults.INCORRECT_PARAMETERS, e)

        # check new process names don't already exist in the config
        for new_config in new_configs:
            for existing_config in group.config.process_configs:
                if new_config.name == existing_config.name:
                    raise RPCError(SupervisorFaults.BAD_NAME, new_config.name)

        # add process configs to group
        group.config.process_configs.extend(new_configs)

        for new_config in new_configs:
            # the process group config already exists and its after_setuid hook
            # will not be called again to make the auto child logs for this process.
            new_config.create_autochildlogs()

            # add process instance
            group.processes[new_config.name] = new_config.make_process(group)

        return True

    def UpdateNumprocs(self, group_name):
        """ graceful process_group numprocs without restart all process when only numprocs changed.
            if numprocs increased, the operation will start (new_num - old_num) processes,
            if numprocs reduced, the operation will stop the last (new_num - old_num) processes
            @param string group_name Name of an existing process group
        """

        try:
            self.supervisord.options.process_config(do_usage=False)
        except ValueError as msg:
            raise RPCError(Faults.CANT_REREAD, msg)

        group = self._getProcessGroup(group_name)
        old_config = self.supervisord.process_groups[group_name].config
        new_config = [ cfg
            for cfg in self.supervisord.options.process_group_configs if cfg.name == group_name
        ][0]
        if old_config == new_config:
            return json.dumps({
                "msg":"No need to update",
                "type":"error"
            })
        else:
            if old_config.name != new_config.name or \
            old_config.priority != new_config.priority:
                return json.dumps({
                    "msg":"Not only numprocs has changed: priority is difference",
                    "type":"error"
                })
            new_process_configs = new_config.process_configs
            old_process_configs = old_config.process_configs
            if len(old_process_configs) < len(new_process_configs):
                if self._issubset(old_process_configs, new_process_configs):
                    return self._add_num(group_name, self._difference(new_process_configs, old_process_configs))
                else:
                    return json.dumps({
                        "msg": "Not only numprocs has chnaged",
                        "type": "error"
                    })
            elif len(old_process_configs) > len(new_process_configs):
                if self._issubset(new_process_configs, old_process_configs):
                    return self._reduce_num(group_name, self._difference(old_process_configs, new_process_configs))
                else:
                    return json.dumps({
                        "msg": "Not only numprocs has changed",
                        "type": "error"
                    })

    # ProcessConfig can't use set because __hash__ is not implemented
    def _difference(self, listA, listB):
        return [ item for item in listA if not self._has(listB, item) ]

    def _has(self, the_list, A):
        for item in the_list:
            if A.__eq__(item):
                return True
        return False

    def _issubset(self, A, B):
        for item in A:
            if not self._has(B, item):
                return False
        return A

    # just return the processes need to remove, let
    # supervisorctl call supervisor to stop the processes
    def _reduce_num(self, group_name, process_configs):
        return json.dumps({
            'processes_name' : ["{0}:{1}".format(group_name,p.name) for p in process_configs],
            'type' : 'reduce'
        })

    def _add_num(self, group_name, new_configs):
        group = self._getProcessGroup(group_name)
        group.config.process_configs.extend(new_configs)

        for new_config in new_configs:
            # the process group config already exists and its after_setuid hook
            # will not be called again to make the auto child logs for this process.
            new_config.create_autochildlogs()

            # add process instance
            group.processes[new_config.name] = new_config.make_process(group)
        return json.dumps({
            'processes_name' : [ "{0}:{1}".format(group_name,p.name) for p in new_configs],
            'type' : 'add'
        })


    def removeProcessFromGroup(self, group_name, process_name):
        """ Remove a process from a process group.  When a program is added with
            addProgramToGroup(), one or more processes for that program is added
            to the group.  This method removes individual processes (named by the
            numprocs and process_name options), not programs.

        @param string group_name    Name of an existing process group
        @param string process_name  Name of the process to remove from group
        @return boolean             Always return True unless error
        """

        group = self._getProcessGroup(group_name)

        # check process exists and is running
        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(SupervisorFaults.BAD_NAME, process_name)


        """ Change to stop process here instead of raise an error
        """
        if process.pid or process.state not in STOPPED_STATES:
            raise RPCError(SupervisorFaults.STILL_RUNNING, process_name)

        group.transition()

        # del process config from group, then del process
        for index, config in enumerate(group.config.process_configs):
            if config.name == process_name:
                del group.config.process_configs[index]

        del group.processes[process_name]
        return True

    def _getProcessGroup(self, name):
        """ Find a process group by its name """
        group = self.supervisord.process_groups.get(name)
        if group is None:
            raise RPCError(SupervisorFaults.BAD_NAME, 'group: %s' % name)
        return group

    def _makeConfigParser(self, section_name, options):
        """ Populate a new UnhosedConfigParser instance with a
        section built from an options dict.
        """
        config = UnhosedConfigParser()
        try:
            config.add_section(section_name)
            for k, v in dict(options).items():
                config.set(section_name, k, v)
        except (TypeError, ValueError):
            raise RPCError(SupervisorFaults.INCORRECT_PARAMETERS)
        return config

def make_grace_rpcinterface(supervisord, **config):
    return GraceNamespaceRPCInterface(supervisord, **config)
