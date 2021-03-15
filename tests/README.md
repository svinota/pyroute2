Warning
=======

Network tests require root access to create, destroy
and set up network objects -- routes, addresses, interfaces,
etc. They use mainly dummy interfaces, thus are
non-destructive. But the integration test cycle includes
stress-tests as well, can take ~20-30 minutes, and should
NOT be run on any production system, since can seriously
affect overall OS performance for a long time.

Requirements
============

* flake8
* nosetests -- for legacy tests
* pytest -- for new tests
* pytest-cov
* coverage
* sphinx
* netaddr

Optionally:

* dtcd

Run legacy tests
================

To run the tests, one can use the root makefile::

    $ sudo make test coverage=html pdb=true

This will also output the coverage in html format and run
pdb debugger in case of errors and failures. Please note,
that by default test cycle runs python with `-W error`. This
causes python 2.x to fail on many systems because of badly
packed system libraries. In that case one can explicitly use
any custom python path (e.g. to python3 or even virtualenv)::

    $ sudo make test python=/usr/bin/python3 ...

It is possible to run only one separate test module, and run
tests in loop:

    $ sudo make test module=general:test_ndb.py loop=1000

More details see in `README.make.md`.

Run new tests
=============

The migration from the legacy nosetests CI to pytest has
just begun, so the pytest CI has not so many options yet.
To run the tests::

    $ sudo make pytest

Get code coverage and run PDB on failures::

    $ sudo make pytest coverage=true pdb=true

Workspaces
==========

The test suite creates dedicated workspaces for every test
run. By default they are created as `$TOP/tests-workspaces/$pid`,
but you can specify another place, e.g. to run tests on tmpfs::

    $ sudo make test \
        module=general:test_ndb.py \
        pdb=true \
        coverage=html \
        workspace=/tmp/pyroute2-test

The coverage report is also created under the workspace directory.

Concurrent testing
==================

Some modules are ready for concurrent testing. It means that one
can run multiple tests in parallel. To do that one should have
dtcd installed, running and listening on port 7623. Sample config::

    $ cat dtcd.conf 
    {
     "version": 1,
     "supernet": "10.0.0.0/8",
     "subnet_mask": 24
    }

dtcd stands for "dynamic test configuration daemon" and is required
to provide tests with unique settings, so tests will use separate
networks and will not conflict deploying files from the git repo.

When dtcd is not available, tests use some preset networks and
conflicts are highly possible, when multiple test runs share
same settings.

This feature is under development yet, so please read the tests
code prior to use it.
