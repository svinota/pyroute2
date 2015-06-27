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

Build documentation. Requires `Sphinx`.

target: epydoc
--------------

Build API documentation. Requires `epydoc`.

Pls notice that epydoc is discontinued. The reason to support
it here is that it performs additional API testing and helps
to highlight API inconsistencies.

No issues regarding epydoc output format are accepted.

target: test
------------

Run tests against current code. Requires `flake8`, `nosetests`,
`coverage`. Command line options:

* python -- the Python to use
* nosetests -- nosetests to use
* wlevel -- the Python -W levels (see Makefile for description)
* coverage -- whether to produce html coverage
* pdb -- whether to run pdb on errors and failures
* module -- run only specific test module
* skip_tests -- skip tests by regexp

Samples::

    $ sudo make test python=python3 coverage=true wlevel=all
    $ sudo make test module=general:test_ipdb.py:TestExplicit
    $ sudo make test skip_tests=test_stress

All tests are divided into several groups (general, lnst, etc).
Every test group is run in a separate python process, so one
can test import statements and safely destroy runtime, as other
test groups will be unaffected.

To run only "general" test group, one can run::

    $ sudo make test module=general:

target: dist
------------

Make Python distribution package. Command line options:

* python -- the Python to use

target: install
---------------

Buidl and install the package into the system. Command line options:

* python -- the Python to use
* root -- root install directory
* lib -- where to install lib files

other targets
-------------

Other targets are either utility targets to be used internally,
or hooks for related projects. You can safely ignore them.
