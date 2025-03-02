dhcp-server-detector
====================

Synopsis
--------

    **dhcp-server-detector [options] interface [interface ...]**

Description
-----------

**dhcp-server-detector** is a DHCP server detection tool based on pyroute2.

It can be used to determine quickly if one or more DHCP server(s) are
responding on one or more network interfaces.
For example, it can be used to detect suspected "rogue" servers, or simply to
probe servers and obtain information about the offered options.

**dhcp-server-detector** sends `DISCOVER` messages on the specified
interface(s) and prints eventual matching `OFFER`:s, and some metadata,
as JSON.

Detection behavior (duration, intervals, ...) can be controlled with a few
options.

Available options
-----------------

--duration <seconds>, -d <seconds>
    Number of seconds spent collecting responses, defaults to 30.

--interval <seconds>, -i <seconds>
    Number of seconds between each `DISCOVER` message, per interface.
    Defaults to 4.

--source-port <port>, -s <port>
    Source port to bind to, defaults to 68.
    It is highly unlikely that you'll ever get any response with another port.

--exit-on-first-offer, -1
    Exit as soon as a response is received.

--log-level <level>
   Logging level to use: `DEBUG`, `INFO`, `WARNING`, `ERROR`.
   The default is `WARNING`.
   Set to `INFO` to log sent & received messages.


Output format
-------------

Each time an `OFFER` is received, a JSON object is printed to stdout.
It contains the following data:

- `interface`, the interface on which the message was received,
- `message`, a full dump of the `OFFER`, with
    - `dhcp`: decoded bootp & dhcp data
    - `eth_src`, `eth_dst`: Link-layer source & destination addresses
    - `ip_src`, `ip_dst`: IPv4 source & destination addresses
    - `sport`, `dport`: UDP source & destination ports.

In proper DHCP, `eth_dst` & `ip_dst` are always broadcast addresses,
and the UDP source & dest. ports are always 67 and 68.


.. code-block:: bash

    # dhcp-server-detector -1 wlp61s0
    {
      "interface": "wlp61s0",
      "message": {
        "dhcp": {
          "op": 2,
          "htype": 1,
          "hlen": 6,
          "hops": 0,
          "xid": 2900208454,
          "secs": 0,
          "flags": 32768,
          "ciaddr": "0.0.0.0",
          "yiaddr": "192.168.94.166",
          "siaddr": "0.0.0.0",
          "giaddr": "0.0.0.0",
          "chaddr": "a0:a4:c5:93:ac:60",
          "sname": "",
          "file": "",
          "cookie": "63:82:53:63",
          "options": {
            "message_type": 2,
            "server_id": "192.168.94.254",
            "lease_time": 43200,
            "subnet_mask": "255.255.255.0",
            "router": [
                "192.168.94.254"
            ],
            "name_server": [
                "192.168.94.254"
            ],
            "broadcast_address": "192.168.94.255"
          }
        },
        "eth_src": "14:0c:76:62:51:64",
        "eth_dst": "ff:ff:ff:ff:ff:ff",
        "ip_src": "192.168.94.254",
        "ip_dst": "255.255.255.255",
        "sport": 67,
        "dport": 68
      }
    }


Exit codes
----------

The programs always exits with `0` if at least one `OFFER` was received
in the configured duration, `1` otherwise.

Along with its JSON output, it means it can be used easily in scripts, like:

.. code-block:: bash

    # prints a line for every interface on which a DHCP server is detected.
    # waits 1 second for each interface.
    for ifname in $(ip --json l | jq -r '.[].ifname'); do
        if dhcp-server-detector -d 1 -1 $ifname > /dev/null; then
            echo "DHCP server found on $ifname"
        fi
    done

or:

.. code-block:: bash
   
    # does the same as the script above, but polls all interfaces in parallel
    # for 3s max before exiting
    dhcp-server-detector -d 3 $(ip --json l | jq -r '.[].ifname') |\
        jq -r .interface
