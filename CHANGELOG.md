Changelog
=========

* 0.5.11
    * ndb.report: filters and transformations
    * ndb.objects.route: support basic MPLS routes management
    * ndb.objects.route: support MPLS lwtunnel routes
    * ndb.schema: reschedule events
* 0.5.10
    * general: don't use pkg_resources <https://github.com/svinota/pyroute2/issues/677>
    * iproute: fix Windows support
    * netlink: provide the target field
    * ndb: use the target field from the netlink header
    * ndb: multiple SQL fixes, transactions fixed with the PostgreSQL backend
    * ndb: multiple object cache fixes <https://github.com/svinota/pyroute2/issues/683>
    * ndb.schema: drop DB triggers
    * ndb.objects: fix object management within a netns <https://github.com/svinota/pyroute2/issues/628>
    * ndb.objects.route: support route metrics
    * ndb.objects.route: fix default route syntax
* 0.5.9
    * ethtool: fix module setup
* 0.5.8
    * ethtool: initial support <https://github.com/svinota/pyroute2/pull/675>
    * tc: multimatch support <https://github.com/svinota/pyroute2/pull/674>
    * tc: meta support <https://github.com/svinota/pyroute2/pull/671>
    * tc: cake: add stats_app decoder <https://github.com/svinota/pyroute2/pull/662>
    * conntrack: filter <https://github.com/svinota/pyroute2/pull/660>
    * ndb.objects.interface: reload after setns
    * ndb.objects.route: create() dst syntax
    * ndb.objects.route: 'default' syntax
    * wireguard: basic testing
* 0.5.7
    * ndb.objects.netns: prototype
    * ndb: netns management
    * ndb: netns sources autoconnect (disabled by default)
    * wireguard: basic support
    * netns: fix FD leakage
        * <https://github.com/svinota/pyroute2/issues/623>
    * cli: Python3 fixes
    * iproute: support `route('append', ...)`
    * ipdb: fix routes cleanup on link down
        * <https://github.com/svinota/pyroute2/issues/620>
    * wiset: support "mark" ipset type
* 0.5.6
    * ndb.objects.route: multipath routes
    * ndb.objects.rule: basic support
    * ndb.objects.interface: veth fixed
    * ndb.source: fix source restart
    * ndb.log: logging setup
* 0.5.5
    * nftables: rules expressions
        * <https://github.com/svinota/pyroute2/pull/592>
    * netns: ns_pids
        * <https://github.com/svinota/pyroute2/pull/593>
    * ndb: wait() method
    * ndb: add extra logging, log state transitions
    * ndb: nested views, e.g. `ndb.interfaces['br0'].ports
    * cli: port pyroute2-cli to use NDB instead of IPDB
    * iproute: basic Windows support (proof of concept only)
    * remote: support mitogen proxy chains, support remote netns
* 0.5.4
    * iproute: basic SR-IOV support, virtual functions setup
    * ipdb: shutdown logging fixed
        * <https://github.com/svinota/pyroute2/issues/553>
    * nftables: fix regression (errata: previously mentioned ipset)
        * <https://github.com/svinota/pyroute2/issues/575>
    * netns: pushns() / popns() / dropns() calls
        * <https://github.com/svinota/pyroute2/pull/590>
* 0.5.3
    * bsd: parser improvements
    * ndb: PostgreSQL support
    * ndb: transactions commit/rollback
    * ndb: dependencies rollback
    * ipdb: IPv6 routes fix
        * <https://github.com/svinota/pyroute2/issues/543>
    * tcmsg: ematch support
    * tcmsg: flow filter
    * tcmsg: stats2 support improvements
    * ifinfmsg: GRE i/oflags, i/okey format fixed
        * <https://github.com/svinota/pyroute2/issues/531>
    * cli/ss2: improvements, tests
    * nlsocket: fix work on kernels < 3.2
        * <https://github.com/svinota/pyroute2/issues/526>
* 0.5.2
    * ndb: read-only DB prototype
    * remote: support communication via stdio
    * general: fix async keyword -- Python 3.7 compatibility
        * <https://github.com/svinota/pyroute2/issues/467>
        * <https://bugzilla.redhat.com/show_bug.cgi?id=1583800>
    * iproute: support monitoring on BSD systems via PF_ROUTE
    * rtnl: support for SQL schema in message classes
    * nl80211: improvements
        * <https://github.com/svinota/pyroute2/issues/512>
        * <https://github.com/svinota/pyroute2/issues/514>
        * <https://github.com/svinota/pyroute2/issues/515>
    * netlink: support generators
* 0.5.1
    * ipdb: #310 -- route keying fix
    * ipdb: #483, #484 -- callback internals change
    * ipdb: #499 -- eventloop interface
    * ipdb: #500 -- fix non-default :: routes
    * netns: #448 -- API change: setns() doesn't remove FD
    * netns: #504 -- fix resource leakage
    * bsd: initial commits
* 0.5.0
    * ACHTUNG: ipdb commit logic is changed
    * ipdb: do not drop failed transactions
    * ipdb: #388 -- normalize IPv6 addresses
    * ipdb: #391 -- support both IPv4 and IPv6 default routes
    * ipdb: #392 -- fix MPLS route key reference
    * ipdb: #394 -- correctly work with route priorities
    * ipdb: #408 -- fix IPv6 routes in tables >= 256
    * ipdb: #416 -- fix VRF interfaces creation
    * ipset: multiple improvements
    * tuntap: #469 -- support s390x arch
    * nlsocket: #443 -- fix socket methods resolve order for Python2
    * netns: non-destructive `netns.create()`
* 0.4.18
    * ipdb: #379 [critical] -- routes in global commits
    * ipdb: #380 -- global commit with disabled plugins
    * ipdb: #381 -- exceptions fixed
    * ipdb: #382 -- manage dependent routes during interface commits
    * ipdb: #384 -- global `review()`
    * ipdb: #385 -- global `drop()`
    * netns: #383 -- support ppc64
    * general: public API refactored (same signatures; to be documented)
* 0.4.17
    * req: #374 [critical] -- mode nla init
    * iproute: #378 [critical] -- fix `flush_routes()` to respect filters
    * ifinfmsg: #376 -- fix data plugins API to support pyinstaller
* 0.4.16
    * ipdb: race fixed: remove port/bridge
    * ipdb: #280 -- race fixed: port/bridge
    * ipdb: #302 -- ipaddr views: [ifname].ipaddr.ipv4, [ifname]ipaddr.ipv6
    * ipdb: #357 -- allow bridge timings to have some delta
    * ipdb: #338 -- allow to fix interface objects from failed `create()`
    * rtnl: #336 -- fix vlan flags
    * iproute: #342 -- the match method takes any callable
    * nlsocket: #367 -- increase default SO_SNDBUF
    * ifinfmsg: support tuntap on armv6l, armv7l platforms
* 0.4.15
    * req: #365 -- full and short nla notation fixed, critical
    * iproute: #364 -- new method, `brport()`
    * ipdb: -- support bridge port options
* 0.4.14
    * event: new genl protocols set: VFS_DQUOT, acpi_event, thermal_event
    * ipdb: #310 -- fixed priority change on routes
    * ipdb: #349 -- fix setting ifalias on interfaces
    * ipdb: #353 -- mitigate kernel oops during bridge creation
    * ipdb: #354 -- allow to explicitly choose plugins to load
    * ipdb: #359 -- provide read-only context managers
    * rtnl: #336 -- vlan flags support
    * rtnl: #352 -- support interface type plugins
    * tc: #344 -- mirred action
    * tc: #346 -- connmark action
    * netlink: #358 -- memory optimization
    * config: #360 -- generic asyncio config
    * iproute: #362 -- allow to change or replace a qdisc
* 0.4.13
    * ipset: full rework of the IPSET_ATTR_DATA and IPSET_ATTR_ADT
      ACHTUNG: this commit may break API compatibility
    * ipset: hash:mac support
    * ipset: list:set support
    * ipdb: throw EEXIST when creates VLAN/VXLAN devs with same ID, but
      under different names
    * tests: #329 -- include unit tests into the bundle
    * legal: E/// logo removed
* 0.4.12
    * ipdb: #314 -- let users choose RTNL groups IPDB listens to
    * ipdb: #321 -- isolate `net_ns_.*` setup in a separate code block
    * ipdb: #322 -- IPv6 updates on interfaces in DOWN state
    * ifinfmsg: allow absolute/relative paths in the net_ns_fd NLA
    * ipset: #323 -- support setting counters on ipset add
    * ipset: `headers()` command
    * ipset: revisions
    * ipset: #326 -- mark types
* 0.4.11
    * rtnl: #284 -- support vlan_flags
    * ipdb: #288 -- do not inore link-local addresses
    * ipdb: #300 -- sort ip addresses
    * ipdb: #306 -- support net_ns_pid
    * ipdb: #307 -- fix IPv6 routes management
    * ipdb: #311 -- vlan interfaces address loading
    * iprsocket: #305 -- support NETLINK_LISTEN_ALL_NSID
* 0.4.10
    * devlink: fix fd leak on broken init
* 0.4.9
    * sock_diag: initial NETLINK_SOCK_DIAG support
    * rtnl: fix critical fd leak in the compat code
* 0.4.8
    * rtnl: compat proxying fix
* 0.4.7
    * rtnl: compat code is back
    * netns: custom netns path support
    * ipset: multiple improvements
* 0.4.6
    * ipdb: #278 -- fix initial ports mapping
    * ipset: #277 -- fix ADT attributes parsing
    * nl80211: #274, #275, #276 -- BSS-related fixes
* 0.4.5
    * ifinfmsg: GTP interfaces support
    * generic: devlink protocol support
    * generic: code cleanup
* 0.4.4
    * iproute: #262 -- `get_vlans()` fix
    * iproute: default mask 32 for IPv4 in `addr()`
    * rtmsg: #260 -- RTA_FLOW support
* 0.4.3
    * ipdb: #259 -- critical `Interface` class fix
    * benchmark: initial release
* 0.4.2
    * ipdb: event modules
    * ipdb: on-demand views
    * ipdb: rules management
    * ipdb: bridge controls
    * ipdb: #258 -- important Python compatibility fixes
    * netns: #257 -- pipe leak fix
    * netlink: support pickling for nlmsg
* 0.4.1
    * netlink: no buffer copying in the parser
    * netlink: parse NLA on demand
    * ipdb: #244 -- lwtunnel multipath fixes
    * iproute: #235 -- route types
    * docs updated
* 0.4.0
    * ACHTUNG: old kernels compatibility code is dropped
    * ACHTUNG: IPDB uses two separate sockets for monitoring and commands
    * ipdb: #244 -- multipath lwtunnel
    * ipdb: #242 -- AF_MPLS routes
    * ipdb: #241, #234 -- fix create(..., reuse=True)
    * ipdb: #239 -- route encap and metrics fixed
    * ipdb: #238 -- generic port management
    * ipdb: #235 -- support route scope and type
    * ipdb: #230, #232 -- routes GC (work in progress)
    * rtnl: #245 -- do not fail if `/proc/net/psched` doesn't exist
    * rtnl: #233 -- support VRF interfaces (requires net-next)
* 0.3.21
    * ipdb: #231 -- return `ipdb.common` as deprecated
* 0.3.20
    * iproute: `vlan_filter()`
    * iproute: #229 -- FDB management
    * general: exceptions re-exported via the root module
* 0.3.19
    * rtmsg: #227 -- MPLS lwtunnel basic support
    * iproute: `route()` docs updated
    * general: #228 -- exceptions layout changed
    * package-rh: rpm subpackages
* 0.3.18
    * version bump -- include docs in the release tarball
* 0.3.17
    * tcmsg: qdiscs and filters as plugins
    * tcmsg: #223 -- tc clsact and bpf direct-action
    * tcmsg: plug, codel, choke, drr qdiscs
    * tests: CI in VMs (see civm project)
    * tests: xunit output
    * ifinfmsg: tuntap support in i386, i686
    * ifinfmsg: #207 -- support vlan filters
    * examples: #226 -- included in the release tarball
    * ipdb: partial commits, initial support
* 0.3.16
    * ipdb: fix the multiple IPs in one commit case
    * rtnl: support veth peer attributes
    * netns: support 32bit i686
    * netns: fix MIPS support
    * netns: fix tun/tap creation
    * netns: fix interface move between namespaces
    * tcmsg: support hfsc, fq_codel, codel qdiscs
    * nftables: initial support
    * netlink: dump/load messages to/from simple types
* 0.3.15
    * netns: #194 -- fix fd leak
    * iproute: #184 -- fix routes dump
    * rtnl: TCA_ACT_BPF support
    * rtnl: ipvlan support
    * rtnl: OVS support removed
    * iproute: rule() improved to support all NLAs
    * project supported by Ericsson
* 0.3.14
    * package-rh: spec fixed
    * package-rh: both licenses added
    * remote: fixed the setup.py record
* 0.3.13
    * package-rh: new rpm for Fedora and CentOS
    * remote: new draft of the remote protocol
    * netns: refactored using the new remote protocol
    * ipdb: gretap support
* 0.3.12
    * ipdb: new `Interface.wait_ip()` routine
    * ipdb: #175 -- fix `master` attribute cleanup
    * ipdb: #171 -- support multipath routes
    * ipdb: memory consumption improvements
    * rtmsg: MPLS support
    * rtmsg: RTA_VIA support
    * iwutil: #174 -- fix FREQ_FIXED flag
* 0.3.11
    * ipdb: #161 -- fix memory allocations
    * nlsocket: #161 -- remove monitor mode
* 0.3.10
    * rtnl: added BPF filters
    * rtnl: LWtunnel support in ifinfmsg
    * ipdb: support address attributes
    * ipdb: global transactions, initial version
    * ipdb: routes refactored to use key index (speed up)
    * config: eventlet support embedded (thanks to Angus Lees)
    * iproute: replace tc classes
    * iproute: flush_addr(), flush_rules()
    * iproute: rule() refactored
    * netns: proxy file objects (stdin, stdout, stderr)
* 0.3.9
    * root imports: #109, #135 -- `issubclass`, `isinstance`
    * iwutil: multiple improvements
    * iwutil: initial tests
    * proxy: correctly forward NetlinkError
    * iproute: neighbour tables support
    * iproute: #147, filters on dump calls
    * config: initial usage of `capabilities`
* 0.3.8
    * docs: inheritance diagrams
    * nlsocket: #126, #132 -- resource deallocation
    * arch: #128, #131 -- MIPS support
    * setup.py: #133 -- syntax error during install on Python2
* 0.3.7
    * ipdb: new routing syntax
    * ipdb: sync interface movement between namespaces
    * ipdb: #125 -- fix route metrics
    * netns: new class NSPopen
    * netns: #119 -- i386 syscall
    * netns: #122 -- return correct errno
    * netlink: #126 -- fix socket reuse
* 0.3.6
    * dhcp: initial release DHCPv4
    * license: dual GPLv2+ and Apache v2.0
    * ovs: port add/delete
    * macvlan, macvtap: basic support
    * vxlan: basic support
    * ipset: basic support
* 0.3.5
    * netns: #90 -- netns setns support
    * generic: #99 -- support custom basic netlink socket classes
    * proxy-ng: #106 -- provide more diagnostics
    * nl80211: initial nl80211 support, iwutil module added
* 0.3.4
    * ipdb: #92 -- route metrics support
    * ipdb: #85 -- broadcast address specification
    * ipdb, rtnl: #84 -- veth support
    * ipdb, rtnl: tuntap support
    * netns: #84 -- network namespaces support, NetNS class
    * rtnl: proxy-ng API
    * pypi: #91 -- embed docs into the tarball
* 0.3.3
    * ipdb: restart on error
    * generic: handle non-existing family case
    * [fix]: #80 -- Python 2.6 unicode vs -O bug workaround
* 0.3.2
    * simple socket architecture
    * all the protocols now are based on NetlinkSocket, see examples
    * rpc: deprecated
    * iocore: deprecated
    * iproute: single-threaded socket object
    * ipdb: restart on errors
    * rtnl: updated ifinfmsg policies
* 0.3.1
    * module structure refactored
    * new protocol: ipq
    * new protocol: nfnetlink / nf-queue
    * new protocol: generic
    * threadless sockets for all the protocols
* 0.2.16
    * prepare the transition to 0.3.x
* 0.2.15
    * ipdb: fr #63 -- interface settings freeze
    * ipdb: fr #50, #51 -- bridge & bond options (initial version)
    * RHEL7 support
    * [fix]: #52 -- HTB: correct rtab compilation
    * [fix]: #53 -- RHEL6.5 bridge races
    * [fix]: #55 -- IPv6 on bridges
    * [fix]: #58 -- vlans as bridge ports
    * [fix]: #59 -- threads sync in iocore
* 0.2.14
    * [fix]: #44 -- incorrect netlink exceptions proxying
    * [fix]: #45 -- multiple issues with device targets
    * [fix]: #46 -- consistent exceptions
    * ipdb: LinkedSet cascade updates fixed
    * ipdb: allow to reuse existing interface in `create()`
* 0.2.13
    * [fix]: #43 -- pipe leak in the main I/O loop
    * tests: integrate examples, import into tests
    * iocore: use own TimeoutException instead of Queue.Empty
    * iproute: default routing table = 254
    * iproute: flush_routes() routine
    * iproute: fwmark parameter for rule() routine
    * iproute: destination and mask for rules
    * docs: netlink development guide
* 0.2.12
    * [fix]: #33 -- release resources only for bound sockets
    * [fix]: #37 -- fix commit targets
    * rtnl: HFSC support
    * rtnl: priomap fixed
* 0.2.11
    * ipdb: watchdogs to sync on RTNL events
    * ipdb: fix commit errors
    * generic: NLA operations, complement and intersection
    * docs: more autodocs in the code
    * tests: -W error: more strict testing now
    * tests: cover examples by the integration testing cycle
    * with -W error many resource leaks were fixed
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

