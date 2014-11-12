Warning
=======

Network tests require the root access to create, destroy
and set up network objects -- routes, addresses, interfaces,
etc. They use mainly fake dummy interfaces, thus are
non-destructive. But the integration test cycle includes
stress-tests as well, can take ~20-30 minutes, and should
NOT be run on any production system, since can seriously
affect overall OS performance for a long time.

Requirements
============

* flake8
* nosetests
* coverage

Run
===

To run tests, one can use the roo makefile::

    $ sudo make test coverage=html pdb=true

This will also output the coverage in html format and run
pdb debugger in case of errors and failures. Please note,
that by default test cycle runs python with `-W error`. This
causes python 2.x to fail on many systems because of badly
packed system libraries. In that case one can explicitly use
any custom python path (e.g. to python3 or even virtualenv)::

    $ sudo make test python=/usr/bin/python3 ...

To run tests manually against the repository::

    $ cd ~/[projects]/pyroute2
    $ flake8 --exclude=docs
    $ export PYTHONPATH=`cwd`
    $ cd tests
    $ sudo nosetests -v

Please remember to add PYTHONPATH to `env_keep` in your
sudo settings.
