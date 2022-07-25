The pyroute2 lab is a collection if interactive tutorials and code samples.

The online version of the lab is here: https://lab.pyroute2.org/

To run the lab examples in the command line, you can use nox:

.. code-block:: shell

   # init the environment from scratch, rebuild the project
   # and install all the dependencies:
   nox -e lab

   # reuse the environment, only build the sphinx project
   # and run the tests
   nox -e lab -r -- '{"reuse": true}'
