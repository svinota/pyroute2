.. modules:

pyroute2 modules
================

The library provides several modules, that operates on different
layers.

iproute
-------

Old-style library, that provides access to rtnetlink as is. It
helps you to retrieve and change almost all the data, available
through rtnetlink::

    from pyroute2 import iproute
    ip = iproute()
        # lookup interface by name
    dev = ip.link_lookup(ifname='tap0')[0]
        # bring it down
    ip.link('set', dev, state='down')
        # change interface MAC address and rename it
    ip.link('set', dev, address='00:11:22:33:44:55', ifname='vpn')
        # add primary IP address
    ip.addr('add', dev, address='10.0.0.1', mask=24)
        # add secondary IP address
    ip.addr('add', dev, address='10.0.0.2', mask=24)
        # bring it up
    ip.link('set', dev, state='up')

ipdb
----

Experimental module, that provides high-level API to network
configuration. It represents network objects as a transactional
database with commit/rollback. It is far not production ready,
so be prepared for surprises and API changes.::

    from pyroute2 import ipdb
    ip = ipdb(mode='direct')
    ip.tap0.down()
    ip.tap0.address = '00:11:22:33:44:55'
    ip.tap0.ifname = 'vpn'
    ip.vpn.up()
    ip.vpn.add_ip('10.0.0.1', 24)
    ip.vpn.add_ip('10.0.0.2', 24)

IPDB has several operating modes:

 * 'direct' -- any change goes immediately to the OS level
 * 'implicit' (default) -- the first change starts an implicit
   transaction, that have to be committed
 * 'explicit' -- you have to begin() a transaction prior to
   make any change
 * 'snapshot' -- no changes will go to the OS in any case

The default is to use implicit transaction. This behaviour can
be changed in the future, so use 'mode' argument when creating
IPDB instances. The sample session with explicit transactions::

    In [1]: from pyroute2 import ipdb
    In [2]: ip = ipdb(mode='explicit')
    In [3]: ip.tap0.begin()
        Out[3]: UUID('7a637a44-8935-4395-b5e7-0ce40d31d937')
    In [4]: ip.tap0.up()
    In [5]: ip.tap0.address = '00:11:22:33:44:55'
    In [6]: ip.tap0.add_ip('10.0.0.1', 24)
    In [7]: ip.tap0.add_ip('10.0.0.2', 24)
    In [8]: ip.tap0.review()
        Out[8]:
        {'+ipaddr': set([('10.0.0.2', 24), ('10.0.0.1', 24)]),
         '-ipaddr': set([]),
         'address': '00:11:22:33:44:55',
         'flags': 4099}
    In [9]: ip.tap0.commit()


Note, that you can `review()` the `last()` transaction, and
`commit()` or `drop()` it. Also, multiple `self._transactions`
are supported, use uuid returned by `begin()` to identify them.

Actually, the form like 'ip.tap0.address' is an eye-candy. The
ipdb objects are dictionaries, so you can write the code above
as that::

    ip['tap0'].down()
    ip['tap0']['address'] = '00:11:22:33:44:55'
    ...

Also, interface objects in transactional mode can operate as
context managers::

    with ip.tap0 as i:
        i.address = '00:11:22:33:44:55'
        i.ifname = 'vpn'
        i.add_ip('10.0.0.1', 24)
        i.add_ip('10.0.0.1', 24)

On exit, the context manager will authomatically `commit()` the
transaction.

IPDB can also create interfaces::

    with ip.create(kind='bridge', ifname='control') as i:
        i.add_port(ip.eth1)
        i.add_port(ip.eth2)
        i.add_ip('10.0.0.1/24')  # the same as i.add_ip('10.0.0.1', 24)

Right now IPDB supports creation of `dummy`, `bond`, `bridge`
and `vlan` interfaces. VLAN creation requires also `link` and
`vlan_id` parameters, see example scripts.

taskstats
---------

All that you should know about taskstats, is that you should not
use it. But if you have to, ok::

    import os
    from pyroute2 import taskstats
    ts = taskstats()
    ts.get_pid_stat(os.getpid())

It is not implemented normally yet, but some methods are already
usable.

