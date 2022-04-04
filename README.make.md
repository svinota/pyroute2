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

target: test
------------

Run the pytest CI. Specific options:

* coverage -- set `coverage=true` to create the coverage report
* pdb -- set `pdb=true` to run pdb in the case of test failure
* skipdb -- skip tests that use a specific DB, `postgres` or `sqlite3`
* dbname -- set the PostgreSQL DB name (if used)

The NDB module uses a DB as the storage, it may be SQLite3 or PostgreSQL.
By default it uses in-memory SQLite3, but tests cover all the providers
as the SQL code may differ. One can skip DB-specific tests by setting
the `skipdb` option.

* python -- path to the Python to use
* wlevel -- the Python -W level
* coverage -- set `coverage=html` to get coverage report
* pdb -- set `pdb=true` to launch pdb on errors
* module -- run only specific test module
* skip -- skip tests by pattern
* loop -- number of test iterations for each module
* report -- url to submit reports to (see tests/collector.py)
* worker -- the worker id

To run the full test cycle on the project, using a specific
python, making html coverage report::

    $ sudo make test python=python3 coverage=true

To run tests in a loop, use the loop parameter::

    $ sudo make test loop=10

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
