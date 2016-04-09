Makefile documentation
======================

Makefile is used to automate Pyroute2 deployment and test
processes. Mostly, it is but a collection of common commands.


target: clean
-------------

Clean up the repo directory from the built documentation,
collected coverage data, compiled bytecode etc.

target: docs
------------

Build documentation. Requires `sphinx`.

target: epydoc
--------------

Build API documentation. Requires `epydoc`.

Pls notice that epydoc is discontinued. The reason to support
it here is that it performs additional API testing and helps
to highlight API inconsistencies.

No issues regarding epydoc output format are accepted.

target: test
------------

Run tests against current code. Command line options:

* python -- path to the Python to use
* nosetests -- path to nosetests to use
* wlevel -- the Python -W level
* coverage -- set `coverage=html` to get coverage report
* pdb -- set `pdb=true` to launch pdb on errors
* module -- run only specific test module
* skip -- skip tests by pattern

To run the full test cycle on the project, using a specific
python, making html coverage report::

    $ sudo make test python=python3 coverage=html

To run a specific test module::

    $ sudo make test module=general:test_ipdb.py:TestExplicit

The module parameter syntax::

    ## module=package[:test_file.py[:TestClass[.test_case]]]

    $ sudo make test module=lnst
    $ sudo make test module=general:test_ipr.py
    $ sudo make test module=general:test_ipdb.py:TestExplicit

There are several test packages:

* general -- common functional tests
* eventlet -- Neutron compatibility tests
* lnst -- LNST compatibility tests

For each package a new Python instance is launched, keep that
in mind since it affects the code coverage collection.

It is possible to skip tests by a pattern::

    $ sudo make test skip=test_stress

target: test-ci
---------------

Run tests on isolated VMs defined by `tests/ci/configs/*xml`.

Requires qemu, kvm, libvirt and civm script: https://github.com/svinota/civm

Command line options:

* civm -- path to the civm script (if it is not in `$PATH`)

target: dist
------------

Make Python distribution package. Command line options:

* python -- the Python to use

target: install
---------------

Build and install the package into the system. Command line options:

* python -- the Python to use
* root -- root install directory
* lib -- where to install lib files

target: develop
---------------

Build the package and deploy the egg-link with setuptools. No code
will be deployed into the system directories, but instead the local
package directory will be visible to the python. In that case one
can change the code locally and immediately test it system-wide
without running `make install`.

* python -- the Python to use

other targets
-------------

Other targets are either utility targets to be used internally,
or hooks for related projects. You can safely ignore them.
