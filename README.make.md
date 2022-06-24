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

* break -- set `break=true` to break CI loops, see comment below
* coverage -- set `coverage=true` to create the coverage report
* dbname -- set the PostgreSQL DB name (if used)
* loop -- number of test iterations for each module
* pdb -- set `pdb=true` to run pdb in the case of test failure
* python -- path to the Python to use
* skipdb -- skip tests that use a specific DB, `postgres` or `sqlite3`
* wlevel -- the Python -W level

The NDB module uses a DB as the storage, it may be SQLite3 or PostgreSQL.
By default it uses in-memory SQLite3, but tests cover all the providers
as the SQL code may differ. One can skip DB-specific tests by setting
the `skipdb` option.

To run the full test cycle on the project, using a specific
python, making html coverage report::

    # make test python=python3 coverage=true

To run tests in a loop, use the loop parameter::

    # make test loop=10 break=true

Test logs may be found in `tests-workspaces`:

* `{pid}/log` -- test logs
* `{pid}/htmlcov` -- coverage report
* `{pid}/*-post.db` -- SQLite3 NDB backups

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
