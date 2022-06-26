Warning
=======

Functional tests under `test_linux` directory require root
access to create, destroy and set up network objects --
routes, addresses, interfaces, etc. They use mainly dummy
interfaces, but the main OS setup may be affected.

Requirements
============

* flake8
* pytest -- for new tests
* pytest-cov
* coverage
* netaddr

Optionally:

* dtcd

Run tests
=========

There are two ways to run the CI sessions. One is tox,
another is to directly run `make test`::

    # using tox
    $ tox -e unit     # run only unit tests
    $ tox -e linter   # run only code checks
    $ sudo tox        # run all the test under root

    # using make
    $ sudo make test                 # Linux functional tests
    $ make test module=test_openbsd  # OpenBSD tests
    $ make test module=test_unit

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
