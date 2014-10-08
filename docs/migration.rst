migration from 0.2.x to 0.3.x
=============================

Though we tried to preserve external API, two branches, `0.2.x` and `0.3.x`,
differ drastically:

* Classes `NetlinkSocket` and `Marshal` moved to `pyroute2.netlink.nlsocket`
* Module `pyroute2.netlink.iproute` moved `pyroute2.iproute`
* Module `pyroute2.netlink.ipdb` moved `pyroute2.ipdb`
* Module `pyroute2.netlink.generic` now is used for Generic Netlink protocol
* Former `pyroute2.netlink.generic` code moved to `pyroute2.netlink`
* Protocol-specific sockets now are described in protocol modules

As before, the root module `pyroute2` re-exports all important classes, so
if you used `from pyroute2 import IPRoute`, nothing changes then.

The most important part of the release `0.3.2` is that all the cluster-specific
code, all the internal messaging etc. was completely deprecated. Since `0.3.2`,
pyroute2 uses only simple threadless socket-like objects to access different
Netlink protocols. The only component, that still uses implicit threads, is the
`IPDB` module.
