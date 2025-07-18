An example echo protocol
------------------------

This directory contains an example of an echo protocol implemented
using Generic Netlink. To load the module, first build it with `make`,
then load it using `insmod`.

.. note:: You must either disable Secure Boot or sign the module to
   load it successfully.

You can use this code as a template for developing your own Generic
Netlink protocols.

Running the client
------------------

To test the module, simply run `netl.py`. It will send a string to the
kernel and print the echoed reply.

Out of scope
------------

The following topics are beyond the scope of this project. Please refer
to external documentation for:

* How to sign kernel modules if Secure Boot is enabled
* How to install kernel build dependencies for your distribution
