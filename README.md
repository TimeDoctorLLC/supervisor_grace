## supervisor_grace

This package is an RPC extension for `Supervisor <http://supervisord.org>`_
that allows you to change the numprocs of the program without restart the
whole program group.

## Installation
I didn't upload it to pypi right now, you can clone this project and install it:
```
git clone https://github.com/wgjak47/supervisor_grace.git
cd supervisor_grace
sudo python2 setup.py install
```

After installing the package, add these lines to your supervisord.conf file to register the twiddler interface:
```
[rpcinterface:grace]
supervisor.rpcinterface_factory = supervisor_grace.rpcinterface:make_grace_rpcinterface

[ctlplugin:grace]
supervisor.ctl_factory = supervisor_grace.controllerplugin:make_grace_controllerplugin

```
You must restart Supervisor for the grace interface to be loaded.

## Usage
We use this programe config as an example:
```
[program:foo]
command=ping google.com             ; the program (relative uses PATH, can take args)
process_name=%(program_name)s_%(process_num)s ; process_name expr (default %(program_name)s)
numprocs=2                    ; number of processes copies to start (def 1)
```

If we change the value of numprocs (3 for example), and update the foo, all the processes will restart:
```
supervisor> update foo
foo: added process group
supervisor> update foo
foo: stopped
foo: updated process group
supervisor> status foo:*
foo:foo_0                        RUNNING   pid 8112, uptime 0:00:05
foo:foo_1                        RUNNING   pid 8113, uptime 0:00:05
foo:foo_2                        RUNNING   pid 8114, uptime 0:00:05
```
But use the grace\_update command will just start the new processes and other processes will not restart:
```
supervisor> grace_update foo
foo:foo_2 added
supervisor> status foo:*
foo:foo_0                        RUNNING   pid 8119, uptime 0:00:20
foo:foo_1                        RUNNING   pid 8120, uptime 0:00:20
foo:foo_2                        RUNNING   pid 8121, uptime 0:00:11
```
And in condition of value of numprocs reduced ( reduce to 2 from 3 for example ), the reduced processes will stop and be removed:
```
supervisor> grace_update foo
foo:foo_2 stoped
foo:foo_2 removed
supervisor> status foo:*
foo:foo_0                        RUNNING   pid 8119, uptime 0:05:36
foo:foo_1                        RUNNING   pid 8120, uptime 0:05:36
```

If not noly numprocs has changed(priority changed for example), grace\_update will not do anything but just output a message:
```
supervisor> grace_update foo
Not only numprocs has changed: priority is difference
```
I suggest you to use update instead.

Author
------

`wgjak47 <http://github.com/wgjak47>`
`This project forked from mnaberez/supervisor_twiddler`
