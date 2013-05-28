Preface
=======

This file contains features not described in the documentation and are
'under construction' yet. Possibly, they can break your system. Be aware.

ipdb.create()
-------------

Creates an interface with an open transaction (implemented)::

    from pyroute2 import ipdb
    ip = ipdb(mode='explicit')
    tid, interface = ip.create('dummy', ifname='bala')
    interface.address = '00:11:22:33:44:55'
    interface.add_ip('10.0.0.1', 24)
    interface.add_ip('10.0.0.2', 24)
    interface.up()
    interface.commit(tid)

Issues:

 * 'direct' mode?
 * should we provide **kwarg, or transaction is enough?
 * what to do on creation time failure?
 * what to do, if creation OK, but transaction fails?

Possible variant::

    from pyroute2 import ipdb
    ip = ipdb(mode='explicit')
    with ip.create('dummy', ifname='bala') as interface:
        interface.address = '00:11:22:33:44:55'
        interface.add_ip('10.0.0.1', 24)
        interface.add_ip('10.0.0.2', 24)
        interface.up()

Issues:

 * then we need to remove `tid` from the `create()` results

