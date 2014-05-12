changelog
=========

* 0.2.10
    * ipdb: command chaining
    * ipdb: fix for RHEL6.5 Python "optimizations"
    * rtnl: support TCA_U32_ACT
    * [fix]: #32 -- NLA comparison
* 0.2.9
    * ipdb: support bridges and bonding interfaces on RHEL
    * ipdb: "shadow" interfaces (still in alpha state)
    * ipdb: minor fixes on routing and compat issues
    * ipdb: as a separate package (sub-module)
    * docs: include ipdb autodocs
    * rpc: include in setup.py
* 0.2.8
    * netlink: allow multiple NetlinkSocket allocation from one process
    * netlink: fix defragmentation for netlink-over-tcp
    * iocore: support forked IOCore and IOBroker as a separate process
    * ipdb: generic callbacks support
    * ipdb: routing support
    * rtnl: #30 -- support IFLA_INFO_DATA for bond interfaces
* 0.2.7
    * ipdb: use separate namespaces for utility functions and other stuff
    * ipdb: generic callbacks (see also IPDB.wait_interface())
    * iocore: initial multipath support 
    * iocore: use of 16byte uuid4 for packet ids
* 0.2.6
    * rpc: initial version, REQ/REP, PUSH/PULL
    * iocore: shared IOLoop
    * iocore: AddrPool usage
    * iproute: policing in FW filter
    * python3 compatibility issues fixed
* 0.2.4
    * python3 compatibility issues fixed, tests passed
* 0.2.3
    * [fix]: #28 -- bundle issue
* 0.2.2
    * iocore: new component
    * iocore: separate IOCore and IOBroker
    * iocore: change from peer-to-peer to flat addresses
    * iocore: REP/REQ, PUSH/PULL
    * iocore: support for UDP PUSH/PULL
    * iocore: AddrPool component for addresses and nonces
    * generic: allow multiple re-encoding
* 0.1.12
    * ipdb: transaction commit callbacks
    * iproute: delete root qdisc (@chantra)
    * iproute: netem qdisc management (@chantra)
* 0.1.11
    * netlink: get qdiscs for particular interface
    * netlink: IPRSocket threadless objects
    * rtnl: u32 policy setup
    * iproute: filter actions, such as `ok`, `drop` and so on
    * iproute: changed syntax of commands, `action` → `command`
    * tests: htb, tbf tests added
* 0.1.10
    * [fix]: #8 -- default route fix, routes filtering
    * [fix]: #9 -- add/delete route routine improved
    * [fix]: #10 -- shutdown sequence fixed
    * [fix]: #11 -- close IPC pipes on release()
    * [fix]: #12 -- stop service threads on release()
    * netlink: debug mode added to be used with GUI
    * ipdb: interface removal
    * ipdb: fail on transaction sync timeout
    * tests: R/O mode added, use `export PYROUTE2_TESTS_RO=True`
* 0.1.9
    * tests: all races fixed
    * ipdb: half-sync commit(): wait for IPs and ports lists update
    * netlink: use pipes for in-process communication
    * Python 2.6 compatibility issue: remove copy.deepcopy() usage
    * QPython 2.7 for Android: works
* 0.1.8
    * complete refactoring of class names
    * Python 2.6 compatibility issues
    * tests: code coverage, multiple code fixes
    * plugins: ptrace message source
    * packaging: RH package
* 0.1.7
    * ipdb: interface creation: dummy, bond, bridge, vlan
    * ipdb: if\_slaves interface obsoleted
    * ipdb: 'direct' mode
    * iproute: code refactored
    * examples: create() examples committed
* 0.1.6
    * netlink: tc ingress, sfq, tbf, htb, u32 partial support
    * ipdb: completely re-implemented transactional model (see docs)
    * generic: internal fields declaration API changed for nlmsg
    * tests: first unit tests committed
* 0.1.5
    * netlink: dedicated io buffering thread
    * netlink: messages reassembling
    * netlink: multi-uplink remote
    * netlink: masquerade remote requests
    * ipdb: represent interfaces hierarchy
    * iproute: decode VLAN info
* 0.1.4
    * netlink: remote netlink access
    * netlink: SSL/TLS server/client auth support
    * netlink: tcp and unix transports
    * docs: started sphinx docs
* 0.1.3
    * ipdb: context manager interface
    * ipdb: [fix] correctly handle ip addr changes in transaction
    * ipdb: [fix] make up()/down() methods transactional [#1]
    * iproute: mirror packets to 0 queue
    * iproute: [fix] handle primary ip address removal response
* 0.1.2
    * initial ipdb version
    * iproute fixes
* 0.1.1
    * initial release, iproute module

