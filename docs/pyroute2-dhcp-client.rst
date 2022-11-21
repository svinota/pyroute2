pyroute2-dhcp-client
====================

Synopsis
--------

    **pyroute2-dhcp-client** <ifname>

Description
-----------

**pyroute2-dhcp-client** is a way too simple DHCP client. The only
option is the network interface to run on. The script prints the
DHCP server response as JSON.

Examples
--------

.. code-block:: bash

    # pyroute2-dhcp-client eth0
    {
        "op": 2,
        "htype": 1,
        "hlen": 6,
        "hops": 0,
        "xid": 17,
        "secs": 0,
        "flags": 0,
        "ciaddr": "0.0.0.0",
        "yiaddr": "172.16.1.105",
        "siaddr": "172.16.1.1",
        "giaddr": "0.0.0.0",
        "chaddr": "18:56:80:11:ff:a3",
        "sname": "",
        "file": "",
        "cookie": "63:82:53",
        "options": {
            "message_type": 5,
            "server_id": "172.16.1.1",
            "lease_time": 43200,
            "renewal_time": 21600,
            "rebinding_time": 37800,
            "subnet_mask": "255.255.255.0",
            "router": [
                "172.16.1.1"
            ],
            "name_server": [
                "172.16.1.1"
            ]
        }
    }
