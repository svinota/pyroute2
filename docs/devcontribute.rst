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

   # run the test cycle on Python 3.10
   #
   sudo tox -e py310

Or using the same virtualenv for the tests:

.. code-block:: bash

   git clone ${pyroute2_git_url}
   cd pyroute2

   python -m venv venv
   . venv/bin/activate
   pip install --upgrade pip

   # dependencies:
   pip install -r tests/requirements.minimal.txt

   # basic code quality checks
   make format

   # run CI
   sudo make test wlevel=once

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
   pip install -r tests/requirements.minimal.txt

   # basic code quality checks
   gmake format

   # test cycle
   gmake test wlevel=once module=test_openbsd

Step 2: make a change
---------------------

The project is designed to work on the bare standard library.
But some embedded environments strip even the stdlib, removing
modules like sqlite3.

So to run pyroute2 even in such environments, the project provdes
to packages, `pyroute2` and `pyroute2.minimal`, with the latter
providing a minimal distribution, but using no sqlite3 or pickle.

Modules `pyroute2` and `pyroute2.minimal` are mutually exclusive.

Each module provides it's own pypi package.
More details: https://github.com/svinota/pyroute2/discussions/786

Step 3: test the change
-----------------------

Assume the environment is already set up on the step 1. Thus:

.. code-block:: bash

   # * run under root to check all the functional tests
   # * run in clear tox environments, thus `-r`
   sudo tox -r

.. warning:: pyroute2 CI does not support parallel tox run, `tox -p`

Step 4: submit a PR
-------------------

The primary repo for the project is on Github. All the PRs
are more than welcome there.

Requirements to a PR
++++++++++++++++++++

The code must comply some requirements:

* the library must work on Python >= 3.6.
* the code must pass `tox -e linter`
* the code must not break existing functional tests
* the `ctypes` usage must not break the library on SELinux
