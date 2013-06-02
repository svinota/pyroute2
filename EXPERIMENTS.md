Preface
=======

This file contains features not described in the documentation and are
'under construction' yet. Possibly, they can break your system. Be aware.

plugin sockets
--------------

Implement plugins for non-netlink data sources:

 * ptrace sockets -- sniff netlink traffic by tracing calls
 * iptables sockets -- get/set iptables rules

ptrace sockets
--------------

(implemented)

Launch a program and analyze netlink traffic::

    ip = IPRoute()
    ip.connect('ptrace://ip link show')
    while True:
        try:
            print(ip.get())
        except Empty:
            break

iptables sockets
----------------

Iptables uses getsockopt()/setsockopt() as a transport.

    ip = IPRoute()
    ip.connect('iptables://local')
