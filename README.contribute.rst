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

   # clone the repo
   git clone ${pyroute2_git_url}
   cd pyroute2

   # run the test suite
   make test

OpenBSD
+++++++

.. code-block:: sh

   # install required tools
   pkg_add bash git gmake gsed python rust

   # clone the repo
   git clone ${pyroute_git_url}
   cd pyroute2

   # run the test suite
   gmake test

Step 2: plan and implement the change
-------------------------------------

The best practice is that any change should be covered by tests.
The test suite is in the `/tests/` folder and is run by `nox`. You
can add your tests to an existing tests module, or create your
own module, if it requires some specific environment that is not
covered yet. In the latter case add a new session to `noxfile.py`.

The project is designed to work on the bare standard library.
But some embedded environments strip even the stdlib, removing
modules like sqlite3.

So to run pyroute2 even in such environments, the project provides
two packages, `pyroute2` and `pyroute2.minimal`, with the latter
providing a minimal distribution, with no sqlite3 or pickle.

Modules `pyroute2` and `pyroute2.minimal` are mutually exclusive.

Each module provides it's own pypi package.
More details: https://github.com/svinota/pyroute2/discussions/786

Step 3: test the change
-----------------------

Assume the environment is already set up on the step 1:

.. code-block:: sh

   # run code linter
   make format

   # run test suite, some tests may require root
   make test

Step 4: submit a PR
-------------------

The primary repo for the project is on Github. All the PRs
are more than welcome there.

Requirements to a PR
++++++++++++++++++++

The code must comply some requirements:

* the library **must** work on Python >= 3.9
* the code **must** pass `make format`
* the code **must** not break existing unit and functional tests (`make test`)
* the `ctypes` usage **must not** break the library on SELinux
