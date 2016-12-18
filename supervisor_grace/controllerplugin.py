from supervisor.supervisorctl import ControllerPluginBase
import pprint
import shlex
import json

class GraceControllerPlugin(ControllerPluginBase):
    def __init__(self, controller):
        self.ctl   = controller
        self.supervisor = controller.get_server_proxy('supervisor')
        self.grace = controller.get_server_proxy('grace')

    def help_grace_update(self):
        self.ctl.output("grace_update xxx\t"
                        "grace_update programe xxx")

    # do graccupdate
    def do_grace_update(self, args):
        splitted = shlex.split(args)
        if len(splitted) != 1:
            return self.help_cache_gupdate()
        groupName = splitted[0]
        result = self.grace.UpdateNumprocs(groupName)
        result = json.loads(result)
        if result['type'] == 'reduce':
            for process in result['processes_name']:
                self.supervisor.stopProcess(process)
                self.ctl.output(process + ' stoped')
            for process in result['processes_name']:
                process_name = process.split(':')[1]
                self.grace.removeProcessFromGroup(groupName, process_name)
                self.ctl.output(process + ' removed')
        # if you set autostart, the added program will autostart
        # otherwise you can start it mannally using supervisorctl start program:*
        elif result['type'] == 'add':
            for process_name in result['processes_name']:
                self.ctl.output(process_name + ' added')
        elif result['type'] == 'error':
            self.ctl.output(result['msg'])

def make_grace_controllerplugin(controller, **config):
    return GraceControllerPlugin(controller)
