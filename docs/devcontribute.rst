.. devcontribute:

Project contribution guide
==========================

To contribute the code to the project, you can use the
github instruments: issues and pull-requests. See more
on the project github page: https://github.com/svinota/pyroute2

Create dev env
++++++++++++++

It is better to use a dedicated VM to run the tests, as the
CI requires root privileges to manage network settings and
network namespaces.

.. code-block:: bash

    git clone https://github.com/svinota/pyroute2.git
    cd pyroute2
    #
    # create a virtual environment
    python -m venv testenv
    #
    # activate it
    . testenv/bin/activate
    #
    # update pip
    pip install --upgrade pip
    #
    # install deps without postgres
    pip install -r tests/requirements.skipdb.txt
    #
    # basic code checks
    make format
    #
    # run basic tests
    # 
    # OBS! ACHTUNG! tests MUST be run under root
    make test skipdb=postgres

Alternatively, one can use tox.

.. code-block:: bash

    #
    tox -e skipdb

Requirements
++++++++++++

The code must comply some requirements:

* the library must work on Python >= 3.6.
* the code must pass `make format`
* the `ctypes` usage must not break the library on SELinux

Testing
+++++++

To perform code tests, run `make test`. Details about
the makefile parameters see in `README.make.md`.
