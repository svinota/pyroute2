.. devmodules:

Modules in progress
===================

There are several modules in the very initial development
state, and the help with them will be particularly
valuable. You are more than just welcome to help with:

.. automodule:: pyroute2.ipset
    :members:

.. automodule:: pyroute2.iwutil
    :members:

Network settings daemon -- pyrouted
-----------------------------------

Pyrouted is a standalone project of a system service, that
utilizes the `pyroute2` library. It consists of a daemon
controlled by `systemd` and a CLI utility that communicates
with the daemon via UNIX socket.

* home: https://github.com/svinota/pyrouted
* bugs: https://github.com/svinota/pyrouted/issues
* pypi: https://pypi.python.org/pypi/pyrouted

It is an extremely simple and basic network interface setup
tool.
