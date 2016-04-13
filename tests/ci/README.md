CI testing
==========

The CI testing requires `civm` -- https://github.com/svinota/civm

Test system requirements
------------------------

The library code will be deployed in the `/opt` directory.
The test system must automatically launch `/etc/rc.d/rc.local`
on the startup, this script will start the test cycle.

Following software must be installed on the system to run
the whole test cycle:

* python-flake8
* python-sphinx
* python-nose
* python-coverage
* python-eventlet
* bridge-utils
* vconfig
* gcc
* make
* tar

Status
------

This is an experimental and unstable part of the
project. Any contributions, hints, issues etc. are
welcome, as usual.
