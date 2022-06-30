Makefile documentation
======================

Makefile is used to automate Pyroute2 deployment and test
processes. Mostly, it is but a collection of common commands.


target: clean
-------------

Clean up the repo directory from the built documentation,
collected coverage data, compiled bytecode etc.

targets: docs, test, format
---------------------------

Run corresponding nox session. Require nox. All other dependencies
will be installed automatically by nox.

target: dist
------------

Make Python distribution package.

target: install
---------------

Build and install the package into the system or the current virtual env.

Requires: pip, twine, build. Or simply use `pip install -r requirements.dev.txt`
