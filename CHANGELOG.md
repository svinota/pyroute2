changelog
=========

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

