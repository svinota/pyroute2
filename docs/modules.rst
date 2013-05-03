.. modules:

pyroute2 modules
================

The library provides several modules, that operates on different
layers.

iproute
-------

Old-style library, that provides access to rtnetlink as is. It
helps you to retrieve and change almost all the data, available
through rtnetlink.::

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
    ip = ipdb()
    ip.tap0.down()
    ip.tap0.address = '00:11:22:33:44:55'
    ip.tap0.ifname = 'vpn'
    ip.tap0.ipaddr.add(('10.0.0.1', 24))
    ip.tap0.ipaddr.add(('10.0.0.2', 24))
    ip.tap0.commit()
    ip.vpn.up()

If you want to review and/or rollback the transaction, you can
use code like that:::

    from pprint import pprint
    ...
    pprint(ip.tap0.review())
        {'attrs': {'address': 'da:72:48:6b:13:c8 -> 00:11:22:33:44:55',
                   'ifname': 'tap0 -> vpn'},
         'ipaddr': ['+10.0.0.4/24',
                    '+10.0.0.5/24',
                    '+10.0.0.2/24',
                    '+10.0.0.3/24',
                    '+10.0.0.1/24']}
    ip.tap0.rollback()

Actually, the form like 'ip.tap0.address' is an eye-candy. The
ipdb objects are dictionaries, so you can write the code above
as that:::

    ip['tap0'].down()
    ip['tap0']['address'] = '00:11:22:33:44:55'
    ip['tap0']['ifname'] = 'vpn'
    ...

Also, interface objects can operate as context managers:::

    with ip.tap0 as i:
        i.address = '00:11:22:33:44:55'
        i.ifname = 'vpn'
        i.ipaddr.add(('10.0.0.1', 24))
        i.ipaddr.add(('10.0.0.1', 24))

On exit, the context manager will authomatically commit the
transaction.

taskstats
---------

All that you should know about taskstats, is that you should not
use it. But if you have to, ok:::

    import os
    from pyroute2 import taskstats
    ts = taskstats()
    ts.get_pid_stat(os.getpid())

It is not implemented normally yet, but some methods are already
usable.

