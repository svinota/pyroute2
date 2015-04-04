
interfaces
==========

 * (+) interface state change
 * (+) ip addresses add/remove
 * create interfaces:
   * (+) bridge
   * (+) bond
   * (+) gre
   * (+) dummy
   * (+) macvlan
   * (+) macvtap
   * (+) tuntap
   * (+) veth
   * (+) vlan
   * (+) vxlan
   * ...
 * (+) bridge and bond ports add/remove
 * (+) bridge management
 * routing
   * (+) add/change/replace/remove
   * (+) metrics

qos
===

 * qdiscs (experimental support since 0.1.6):
   * (+) sfq
   * (+) tbf
   * (+) ingress
   * (+) netem
   * (+) htb
   * ...
 
 * filters: 
   * (+) u32 (partly implemented, no docs yet)
   * ...   

specific ipdb
=============

 * transaction modes
   * (+) direct mode: changes go immediately to the OS
   * (+) implicit mode: the first change starts the transaction
   * (+) explicit mode: one have to start the transaction first

message types
=============

 * NETLINK_ROUTE
   * (+) ndmsg: ARP cache entries
   * (+) rtmsg: routing classes
   * (+) ifaddrmsg: address management
   * (+) ifinfmsg: interface management
   * (+) tcmsg: traffic control, qdiscs & classes & filters
 * TASKSTATS
   * (+) get stats for pid
   * (-) get stats for tgid
   * (-) subscribe for taskstats events
 * ...

testing
=======

 * (+) unit tests: started
 * (+) read/write access: interfaces and addresses changes
 * (+) coverage

Coverage status: http://pyroute2.org/coverage/
