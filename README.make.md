Makefile documentation
======================

Makefile is used to automate Pyroute2 deployment and test
processes. Mostly, it is but a collection of common commands.

Targets
-------

clean
+++++

Clean up the repo directory from the built documentation,
collected coverage data, compiled bytecode etc.

docs
++++

Build documentationr. Requires `Sphinx`.

test
++++

Run tests against current code. Requires `flake8`, `nosetests`,
`coverage`. Command line options:

* python -- the Python to use
* nosetests -- nosetests to use
* wlevel -- the Python -W levels (see Makefile for description)
* coverage -- whether to produce html coverage
* pdb -- whether to run pdb on errors and failures

Sample::

    $ sudo make test python=python3 coverage=true wlevel=all

Please notice, that by default tests run with wlevel=error,
thus failing on *any* warning.

dist
++++

Make Python distribution package. Command line options:

* python -- the Python to use

install
+++++++

Buidl and install the package into the system. Command line options:

* python -- the Python to use
* root -- root install directory
* lib -- where to install lib files

other targets
+++++++++++++

Other targets are either utility targets to be used internally,
or hooks for related projects. You can safely ignore them.
