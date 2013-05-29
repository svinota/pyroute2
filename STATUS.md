
interfaces
==========

 * (+) interface state change
 * (+) ip addresses add/remove
 * create interfaces:
   * (+) dummy
   * (+) bridge
   * (+) bond
   * (+) vlan
   * ...
 * (+) bridge and bond ports add/remove
 * routing: only low-level functions yet, no docs
   * ...

qos
===

 * qdiscs (experimental support since 0.1.6):
   * (-) [0.2.0] pfifo_fast
   * (+) sfq
   * (+) tbf
   * (+) ingress
   * (-) [0.2.0] htb (partly implemented, no docs yet)
   * ...
 
 * filters: 
   * (-) [0.2.0] u32 (partly implemented, no docs yet)
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
 * IPTABLES
   * (-) [0.2.0] planned
 * IPQ etc.
   * (-) [0.2.1] planned

testing
=======

 * (+) unit tests: started
 * (-) read/write access: interfaces and addresses changes
 * (-) coverage
