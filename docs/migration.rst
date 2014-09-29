migration from 0.2.x to 0.3.x
=============================

* Classes `NetlinkSocket` and `Marshal` moved to `pyroute2.netlink.nlsocket`
* Module `pyroute2.netlink.iproute` moved `pyroute2.iproute`
* Module `pyroute2.netlink.ipdb` moved `pyroute2.ipdb`
* Module `pyroute2.netlink.generic` now is used for Generic Netlink protocol
* Former `pyroute2.netlink.generic` code moved to `pyroute2.netlink`
* Protocol-specific sockets now are described in protocol modules

As before, the root module `pyroute2` re-exports all important classes, so
if you used `from pyroute2 import IPRoute`, nothing changes then.
