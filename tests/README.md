Test modules
============

* `test_limits` -- resource limits, fd leaks, etc
* `test_linux` -- functional tests for Linux, may require root
* `test_minimal` -- test pyroute2.minimal package
* `test_neutron` -- integration with OpenStack Neutron
* `test_noxfile` -- noxfile.py static checks
* `test_openbsd` -- functional tests for OpenBSD
* `test_unit` -- unittests

Functional tests under `test_linux` directory require root
access to create, destroy and set up network objects --
routes, addresses, interfaces, etc. They use mainly dummy
interfaces, but the main OS setup may be affected.

Requirements
============

* nox
* python >= 3.6
* `-r requirements.dev.txt`

Run tests
=========

All the tests should be started via corresponding nox session,
see `noxfile.py`. Alternatively there is a `make` target left
for those who prefer::

    # using nox
    $ nox --list
    $ nox -e unit                     # run only unit tests
    $ nox -e unit -- '{"pdb": true}'  # provide a session config
    $ nox                             # run all the tests

    # using make
    $ sudo make test                 # run the default sessions
    $ make test session=unit         # run only unit tests
    $ make test session=openbsd      # OpenBSD tests

Get code coverage and run PDB on failures::

    $ nox -e linux -- '{"pdb": true, "coverage": true}'
