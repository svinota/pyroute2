Report a bug
============

In the case you have issues, please report them to the project
bug tracker: https://github.com/svinota/pyroute2/issues

It is important to provide all the required information
with your report:

* Linux kernel version
* Python version
* Specific environment, if used -- gevent, eventlet etc.

The project provides a script to print the system summary:

.. code-block:: sh

    pyroute2-test-platform

Please keep in mind, that this command will try to create
and delete different interface types, and this requires
root access.

It is possible also to run the test in your code:

.. code-block:: python

    from pprint import pprint
    from pyroute2.config.test_platform import TestCapsRtnl
    pprint(TestCapsRtnl().collect())
