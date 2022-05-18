.. devcontribute:

Project contribution guide
==========================

Step 1: setup the environment
-----------------------------

Linux
+++++

.. code-block:: bash

   # make sure you have installed:
   #   bash
   #   git
   #   python
   #   GNU make
   #   GNU sed
   #
   # then clone the repo
   git clone ${pyroute2_git_url}
   cd pyroute2

   # create and activate virtualenv
   python -m venv venv
   . venv/bin/activate

   # update pip and install tox
   pip install --upgrade pip
   pip install tox

   # run the fast test cycle
   #
   # OBS! ACHTUNG! functional tests require root on Linux
   sudo tox -e skipdb

Or using the same virtualenv for the tests:

.. code-block:: bash

   git clone ${pyroute2_git_url}
   cd pyroute2
   python -m venv venv
   . venv/bin/activate
   pip install --upgrade pip

   # dependencies:
   pip install -r tests/requirements.skipdb.txt

   # basic code quality checks
   make format

   # fast test cycle
   # OBS! ACHTUNG! functional tests require root on Linux
   sudo make test wlevel=error skipdb=postgres

OpenBSD
+++++++

.. code-block:: bash

   # install required tools
   pkg_add bash git gmake gsed python

   # clone the repo
   git clone ${pyroute_git_url}
   cd pyroute2

   # create and activate virtualenv
   python3.10 -m venv venv
   . venv/bin/activate

   # update pip and install tox
   pip install --upgrade pip
   pip install tox

   # run the platform specific environment
   tox -e openbsd

Or using the same virtualenv for the tests:

.. code-block:: bash

   git clone ${pyroute2_git_url}
   cd pyroute2
   python -m venv venv
   . venv/bin/activate
   pip install --upgrade pip

   # dependencies:
   pip install -r tests/requirements.skipdb.txt

   # basic code quality checks
   gmake format

   # test cycle
   gmake test wlevel=error make=gmake

Step 2: make a change
---------------------

The project is designed to work on the bare standard library.
But some embedded environments strip even the stdlib, removing
modules like sqlite3.

So to run pyroute2 even in such environments, the project is
divided into separate modules, one can install the very minimal
pyroute2 core.

The repo layout is as follows:

.. code-block::

   * pyroute2
     * requires all the project modules
     * contains the main init file
   * pyroute2.minimal
     * requires only the core
     * same init file
   * pyroute2.core
     * the main module, core netlink protocols
   * pyroute2.{module}
     * extensions, user-friendly APIs etc.

All the modules except `pyroute2` and `pyroute2.minimal` install the code
into the same `pr2modules` namespace.

Modules `pyroute2` and `pyroute2.minimal` are mutually exclusive, their
goal is to provide correct dependencies and re-export modules from the
`pr2modules` namespace to `pyroute2`.

Each module provides it's own pypi package.
More details: https://github.com/svinota/pyroute2/discussions/786

The tradeoff of this approach is that it's a bit tricky to use autocomplete
and symbols lookup in IDEs.

Step 3: test the change
-----------------------

Assume the environment is already set up on the step 1. Thus:

.. code-block:: bash

   # fast check on Linux
   # skip NDB PostgreSQL integration tests
   tox -e skipdb

   # on OpenBSD
   tox -e openbsd

Step 4: submit a PR
-------------------

The primary repo for the project is on Github. All the PRs
are more than welcome there.

Requirements to a PR
++++++++++++++++++++

The code must comply some requirements:

* the library must work on Python >= 3.6.
* the code must pass `make format`
* the code must not break existing functional tests
* the `ctypes` usage must not break the library on SELinux
