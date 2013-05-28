Preface
=======

This file contains features not described in the documentation and are
'under construction' yet. Possibly, they can break your system. Be aware.

ipdb.create()
-------------

Creates an interface with an open transaction::

    from pyroute2 import ipdb
    ip = ipdb(mode='explicit')
    i = ip.create(kind='dummy', ifname='bala')
    i.address = '00:11:22:33:44:55'
    i.add_ip('10.0.0.1', 24)
    i.add_ip('10.0.0.2', 24)
    i.up()
    i.commit()

Issues:

 * 'direct' mode?
 * (+) should we provide **kwarg, or transaction is enough? (ok)
 * (+) what to do on creation time failure? (invalidate interface)
 * (+) what to do, if creation OK, but transaction fails? (as usual, drop())

As a context manager::

    from pyroute2 import ipdb
    ip = ipdb(mode='explicit')
    with ip.create(kind='dummy', ifname='bala') as i:
        i.address = '00:11:22:33:44:55'
        i.add_ip('10.0.0.1', 24)
        i.add_ip('10.0.0.2', 24)
        i.up()
