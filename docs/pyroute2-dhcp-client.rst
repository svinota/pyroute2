pyroute2-dhcp-client
====================

Synopsis
--------

    **pyroute2-dhcp-client** [OPTION]... <ifname>

Description
-----------

**pyroute2-dhcp-client** is a client based on the pyroute2 DHCP implementation.

It is mostly a simple CLI wrapper around the
`pyroute2.dhcp.client.AsyncDHCPClient` class, which has more flexibility and
configuration options (see `pyroute2.dhcp.client.ClientConfig`).
Some options are not (yet) configurable through the commandline, such as the
client and vendor IDs, the hostname and the requested parameters.

Its default behavior is to try to acquire a lease for the passed interface,
configuring its IP address and gateway, as long as it is running.
On exit, it releases its lease and remove the associated IP from the interface.
If the interface goes down during the client's lifetime, or is not up when
starting, the client waits until it is up again.

System configuration based on lease options (i.e. IP/gateway configuration)
is done through hooks. The default hooks add the obtained IP to the interface
and set the default gateway, but that can be configured, and you can ask the
client to run your own custom hooks (see `pyroute2.dhcp.hooks`).

The client can also be started in "one-shot" mode (see the `-x` option), where
it will exit as soon as a lease is obtained.

Available options:
------------------

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

--write-pidfile, -p
    Write a pid file in the working directory.

Leases
------

The default behavior is to write the latest obtained lease to a JSON file named
after the interface in the client's working directory.

On startup, if the client finds such a file, it will request the same IP.

This behavior can be modified with the `--lease-type` option. For example, the
`pyroute2.dhcp.client.leases.JSONStdoutLease` class just writes leases to
standard output and does not persist them to disk.

Signals
-------

**pyroute2-dhcp-client** responds to the following signals:

- `SIGINT` (i.e. Ctrl-C) releases & exits
- `SIGUSR1` triggers a lease renewal (normally triggered automatically at ~50% of the lease time)
- `SIGUSR2` triggers a rebinding (normally triggered automatically at ~87% of the lease time)
- `SIGHUP` forces the current lease to expire and starts looking for a new one

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
