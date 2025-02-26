.. sockets:

Module architecture
^^^^^^^^^^^^^^^^^^^

Sockets
=======

The idea behind the pyroute2 framework is pretty simple. The
library provides socket objects, that have:

* shortcuts to establish higher level connections (netlink, 9p, ...)
* extra methods to run queries and protocols

The library core is based on asyncio, and provides both asynchronous
and synchronous versions of API, where the synchronous one is a
wrapper around the async code. This way we avoid keeping two separate
codebase while providing the legacy sync API.

The library provides asynchronous sockets:

.. inheritance-diagram:: pyroute2.iproute.linux.AsyncIPRoute
    pyroute2.netlink.rtnl.iprsocket.AsyncIPRSocket
    pyroute2.plan9.client.Plan9ClientSocket
    pyroute2.plan9.server.Plan9ServerSocket
    pyroute2.dhcp.dhcp4socket.AsyncDHCP4Socket
    :parts: 1

And syncronous sockets:

.. inheritance-diagram:: pyroute2.iproute.linux.IPRoute
    pyroute2.iproute.linux.IPRoute
    pyroute2.iproute.linux.RawIPRoute
    pyroute2.netlink.rtnl.iprsocket.IPRSocket
    pyroute2.iwutil.IW
    pyroute2.ipset.IPSet
    pyroute2.ipvs.IPVS
    pyroute2.netlink.uevent.UeventSocket
    pyroute2.netlink.taskstats.TaskStats
    pyroute2.netlink.generic.wireguard.WireGuard
    pyroute2.netlink.generic.ethtool.NlEthtool
    pyroute2.netlink.ipq.IPQSocket
    pyroute2.netlink.nfnetlink.nfctsocket.NFCTSocket
    pyroute2.netlink.nfnetlink.nftsocket.NFTSocket
    pyroute2.netlink.event.EventSocket
    pyroute2.netlink.event.acpi_event.AcpiEventSocket
    pyroute2.netlink.event.dquot.DQuotSocket
    pyroute2.netlink.event.thermal.ThermalEventSocket
    pyroute2.netlink.devlink.DevlinkSocket
    pyroute2.netlink.diag.DiagSocket
    :parts: 1

Not all the synchronous sockets have got their asynchronous counterpart yet,
but this work is ongoing.

Netlink messages
================

To handle the data going through the sockets, the library
uses different message classes. To create a custom message
type, one should inherit:

    * `nlmsg` to create a netlink message class
    * `genlmsg` to create generic netlink message class
    * `nla` to create a NLA class

The messages hierarchy:

.. inheritance-diagram:: pyroute2.netlink.rtnl.ndmsg.ndmsg
    pyroute2.netlink.rtnl.ndtmsg.ndtmsg
    pyroute2.netlink.rtnl.tcmsg.tcmsg
    pyroute2.netlink.rtnl.rtmsg.nlflags
    pyroute2.netlink.rtnl.rtmsg.rtmsg_base
    pyroute2.netlink.rtnl.rtmsg.rtmsg
    pyroute2.netlink.rtnl.rtmsg.nh
    pyroute2.netlink.rtnl.fibmsg.fibmsg
    pyroute2.netlink.rtnl.ifaddrmsg.ifaddrmsg
    pyroute2.netlink.rtnl.ifstatsmsg.ifstatsmsg
    pyroute2.netlink.rtnl.ifinfmsg.ifinfmsg
    pyroute2.netlink.rtnl.ifinfmsg.ifinfveth
    pyroute2.netlink.rtnl.iw_event.iw_event
    pyroute2.netlink.rtnl.nsidmsg.nsidmsg
    pyroute2.netlink.rtnl.nsinfmsg.nsinfmsg
    pyroute2.netlink.rtnl.rtgenmsg.rtgenmsg
    pyroute2.netlink.devlink.devlinkcmd
    pyroute2.netlink.diag.inet_addr_codec
    pyroute2.netlink.diag.inet_diag_req
    pyroute2.netlink.diag.inet_diag_msg
    pyroute2.netlink.diag.unix_diag_req
    pyroute2.netlink.diag.unix_diag_msg
    pyroute2.netlink.event.acpi_event.acpimsg
    pyroute2.netlink.event.dquot.dquotmsg
    pyroute2.netlink.event.thermal.thermal_msg
    pyroute2.netlink.taskstats.taskstatsmsg
    pyroute2.netlink.taskstats.tcmd
    pyroute2.netlink.generic.ethtool.ethtool_strset_msg
    pyroute2.netlink.generic.ethtool.ethtool_linkinfo_msg
    pyroute2.netlink.generic.ethtool.ethtool_linkmode_msg
    pyroute2.netlink.generic.ethtool.ethtool_linkstate_msg
    pyroute2.netlink.generic.ethtool.ethtool_wol_msg
    pyroute2.netlink.generic.wireguard.wgmsg
    pyroute2.netlink.ctrlmsg
    pyroute2.netlink.genlmsg
    pyroute2.netlink.nl80211.nl80211cmd
    pyroute2.netlink.nfnetlink.ipset.ipset_msg
    pyroute2.netlink.nfnetlink.nfgen_msg
    pyroute2.netlink.nfnetlink.nftsocket.nft_gen_msg
    pyroute2.netlink.nfnetlink.nftsocket.nft_chain_msg
    pyroute2.netlink.nfnetlink.nftsocket.nft_rule_msg
    pyroute2.netlink.nfnetlink.nftsocket.nft_set_msg
    pyroute2.netlink.nfnetlink.nftsocket.nft_table_msg
    pyroute2.netlink.nfnetlink.nfctsocket.nfct_stats
    pyroute2.netlink.nfnetlink.nfctsocket.nfct_stats_cpu
    pyroute2.netlink.nfnetlink.nfctsocket.nfct_msg
    pyroute2.netlink.ipq.ipq_mode_msg
    pyroute2.netlink.ipq.ipq_packet_msg
    pyroute2.netlink.ipq.ipq_verdict_msg
    pyroute2.netlink.uevent.ueventmsg
    :parts: 1

PF_ROUTE messages
=================

PF_ROUTE socket is used to receive notifications from the BSD
kernel. The PF_ROUTE messages:

.. inheritance-diagram:: pyroute2.bsd.pf_route.freebsd.bsdmsg
    pyroute2.bsd.pf_route.freebsd.if_msg
    pyroute2.bsd.pf_route.freebsd.rt_msg_base
    pyroute2.bsd.pf_route.freebsd.ifa_msg_base
    pyroute2.bsd.pf_route.freebsd.ifma_msg_base
    pyroute2.bsd.pf_route.freebsd.if_announcemsg
    pyroute2.bsd.pf_route.rt_slot
    pyroute2.bsd.pf_route.rt_msg
    pyroute2.bsd.pf_route.ifa_msg
    pyroute2.bsd.pf_route.ifma_msg
    :parts: 1

Internet protocols
==================

Beside of the netlink protocols, the library implements a
limited set of supplementary internet protocol to play with.

.. inheritance-diagram:: pyroute2.protocols.udpmsg
    pyroute2.protocols.ip4msg
    pyroute2.protocols.udp4_pseudo_header
    pyroute2.protocols.ethmsg
    pyroute2.dhcp.dhcp4msg.dhcp4msg
    :parts: 1
