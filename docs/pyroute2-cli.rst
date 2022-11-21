pyroute2-cli
============

Synopsis
--------

    cat script_file | **pyroute2-cli** [options]

    **pyroute2-cli** [options] script_file

Description
-----------

**pyroute2-cli** is an interface towards pyroute2 NDB -- network database.
It can provide both CLI and HTTP interfaces.

Status
------

**pyroute2-cli** is a proof-of-concept for now, it has some auth framework,
but no support for SSL. Don't hesitate to file feature requests and bugs on
the project page.

Options
-------

.. program:: pyroute2-cli

.. option:: -m <C|S>

   Mode to use: C (cli, by default) or S (server)

.. rubric:: **CLI mode options**

.. option:: -c <cmd>

   Command line to run
 
.. option:: -r <file>

   An rc file to load before the session

.. option:: -s <file>

   Load sources spec from a JSON file

.. option:: -l <spec>

   Log spec

.. rubric:: **Server mode options**

.. option:: -a <ipaddr>

   IP address to listen on

.. option:: -p <port>

   TCP port to listen on

.. option:: -s <file>

   Load sources spec from a JSON file

.. option:: -l <spec>

   Log spec

Examples
--------

Running CLI:

.. code-block:: bash

    # bring eth0 up and add an IP address
    pyroute2-cli -l debug -c "interfaces eth0 set { state up } => add_ip { 10.0.0.2/24 } => commit"

    # same via stdin + pipe:
    cat <<EOF | pyroute2-cli                                                                
    > interfaces eth0
    >     set { state up }
    >     add_ip { 10.0.0.2/24 }
    >     commit
    > EOF

    # run a script from a file script.pr2:
    interfaces eth0
          set { state up }
          add_ip { 10.0.0.2/24 }
          commit

    pyroute2-cli -l debug script.pr2

The server mode:

.. code-block:: bash

   # start the server
   pyroute2-cli -l debug -m S -a 127.0.0.1 -p 8080

   # run a request
   # text/plain: send a text script to the server
   curl \
       -H "Content-Type: text/plain" \
       -d "neighbours summary | format json" \
       http://localhost:8080/v1/

   # application/json: send a script as a JSON data
   curl \
       -H "Content-Type: application/json" \
       -d '{"commands": ["neighbours summary | format json"]}'
       http://localhost:8080/v1/
   
   curl \
       -H "Content-Type: application/json" \
       -d '{"commands": ["interfaces eth0", "set state down", "commit"]}'
       http://localhost:8080/v1/
