.. devcontribute:

Project contribution guide
==========================

Step 1: setup the environment
-----------------------------

Linux
+++++

.. code-block:: sh

   # make sure you have installed:
   #   bash
   #   git
   #   python
   #   GNU make, sed, awk
   #
   # then clone the repo
   git clone ${pyroute2_git_url}
   cd pyroute2

   # create and activate virtualenv
   python -m venv venv
   . venv/bin/activate

   # update pip and install nox
   pip install --upgrade pip
   pip install nox

   # run the test cycle
   nox

OpenBSD
+++++++

.. code-block:: sh

   # install required tools
   pkg_add bash git gmake gsed python

   # clone the repo
   git clone ${pyroute_git_url}
   cd pyroute2

   # create and activate virtualenv
   python3.10 -m venv venv
   . venv/bin/activate

   # update pip and install nox
   pip install --upgrade pip
   pip install nox

   # run the platform specific environment
   nox -e openbsd

Step 2: make a change
---------------------

The project is designed to work on the bare standard library.
But some embedded environments strip even the stdlib, removing
modules like sqlite3.

So to run pyroute2 even in such environments, the project provdes
two packages, `pyroute2` and `pyroute2.minimal`, with the latter
providing a minimal distribution, but using no sqlite3 or pickle.

Modules `pyroute2` and `pyroute2.minimal` are mutually exclusive.

Each module provides it's own pypi package.
More details: https://github.com/svinota/pyroute2/discussions/786

Step 3: test the change
-----------------------

Assume the environment is already set up on the step 1. Thus:

.. code-block:: sh

   # run code checks
   nox -e linter

   # run unit tests
   nox -e unit

   # run functional test, some require root
   nox -e linux-3.10

Step 4: submit a PR
-------------------

The primary repo for the project is on Github. All the PRs
are more than welcome there.

Requirements to a PR
++++++++++++++++++++

The code must comply some requirements:

* the library must work on Python >= 3.6.
* the code must pass `nox -e linter`
* the code must not break existing unit and functional tests
* the `ctypes` usage must not break the library on SELinux
