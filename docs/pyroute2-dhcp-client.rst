pyroute2-dhcp-client
====================

Synopsis
--------

    **pyroute2-dhcp-client** [OPTION]... <ifname>

Description
-----------

**pyroute2-dhcp-client** is a DHCP client based on pyroute2 DHCP protocol
implementation. Available options:

--lease-type <type>
    Class to use for leases. Must be a subclass of `pyroute2.dhcp.leases.Lease`.

--hook <hook>
    Hooks to run on lease events, see `pyroute2.dhcp.hooks`.

--disable-hooks
    Disable all hooks.

--exit-on-timeout <N>, -x <N>
    Wait for max N seconds for a lease, exit if none could be obtained.

--log-level <level>
    Logging level to use: DEBUG, INFO, WARNING, ERROR. The default is INFO.

--no-release, -R
    Do not send a DHCPRELEASE on exit.

**Warning**: these options can be removed or changed in next releases:

--write-pidfile, -p
    Write a pid file in the working directory.

Examples
--------

.. code-block:: bash

    # pyroute2-dhcp-client --disable-hooks -R -x 5 eth0
    ...
    # cat eth0.lease.json
    {
      "ack": {
        "op": 2,
        "htype": 1,
        "hlen": 6,
        "hops": 0,
        "xid": 391458644,
        "secs": 0,
        "flags": 32768,
        "ciaddr": "0.0.0.0",
        "yiaddr": "192.168.124.180",
        "siaddr": "192.168.124.1",
        "giaddr": "0.0.0.0",
        "chaddr": "aa:80:fa:2c:49:a2",
        "sname": "",
        "file": "",
        "cookie": "63:82:53:63",
        "options": {
          "message_type": 5,
          "server_id": "192.168.124.1",
          "lease_time": 3600,
          "renewal_time": 1800,
          "rebinding_time": 3150,
          "subnet_mask": "255.255.255.0",
          "broadcast_address": "192.168.124.255",
          "router": [
            "192.168.124.1"
          ],
          "name_server": [
            "192.168.124.1"
          ]
        }
      },
      "interface": "eth0",
      "server_mac": "52:54:00:e9:d3:1d",
      "obtained": 1740562827.7350075
    }
