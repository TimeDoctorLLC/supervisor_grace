from supervisor.supervisorctl import ControllerPluginBase
import pprint
import shlex
import json

class GraceControllerPlugin(ControllerPluginBase):
    def __init__(self, controller):
        self.ctl   = controller
        self.supervisor = controller.get_server_proxy('superviosr')
        self.grace = controller.get_server_proxy('grace')

    def help_cache_count(self):
        self.ctl.output("cache_count\t"
                        "Get a count of all items in the cache.")

    # do graccupdate
    def do_grace_gupdate(self, args):
        splitted = shlex.split(args)
        if len(splitted) != 1:
            return self.help_cache_gupdate()
        groupName = splitted[0]
        result = self.grace.gracefulupdate(groupName)
        result = json.loads(result)
        if result['type'] == 'reduce':
            for process in result['processes_name']:
                self.supervisor.stopProcess(process)
            for process in result['processes_name']:
                self.grace.removeProcessFromGroup(self, groupName, process)
        elif result['type'] == 'add':
            for process in result['processes_name']:
                self.supervisor.startProcess(process)
        elif result['type'] == 'error':
            self.ctl.output(result['error_msg'])

def make_cache_controllerplugin(controller, **config):
    return CacheControllerPlugin(controller)
