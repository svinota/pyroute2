from pr2test.tools import interface_exists
from pr2test.tools import address_exists
from pr2test.tools import route_exists


def test_cm_interface_create(context):
    '''
    Create an interface using context manager syntax
    '''
    ifname = context.new_ifname
    with context.ndb.interfaces.create(
            ifname=ifname,
            kind='dummy',
            state='down'):
        pass
    assert interface_exists(context.netns, ifname=ifname, state='down')
    return ifname


def test_cm_address_create(context):
    '''
    Create an address using context manager syntax
    '''
    ifname = test_cm_interface_create(context)
    ipaddr = context.new_ipaddr
    with context.ndb.addresses.create(
            index=context.ndb.interfaces[ifname]['index'],
            address=ipaddr,
            prefixlen=24):
        pass
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)


def test_cm_interface_change_assign(context):
    '''
    ::
        with interface as i:
            i['state'] = 'up'
    '''
    ifname = test_cm_interface_create(context)
    with context.ndb.interfaces[ifname] as i:
        i['state'] = 'up'
    assert interface_exists(context.netns, ifname=ifname, state='up')


def test_cm_interface_change_set_argv(context):
    '''
    ::
        with interface as i:
            i.set('state', 'up')
    '''
    ifname = test_cm_interface_create(context)
    with context.ndb.interfaces[ifname] as i:
        i.set('state', 'up')
    assert interface_exists(context.netns, ifname=ifname, state='up')


def test_cm_interface_change_set_kwarg(context):
    '''
    ::
        with interface as i:
            i.set(state='up')
    '''
    ifname = test_cm_interface_create(context)
    with context.ndb.interfaces[ifname] as i:
        i.set(state='up')
    assert interface_exists(context.netns, ifname=ifname, state='up')


def test_routes_spec_dst_len(context):

    ipaddr = context.new_ipaddr
    gateway = context.new_ipaddr
    ifname = context.new_ifname
    ipnet = str(context.ipnets[1].network)
    table = 24000

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .add_ip(address=ipaddr, prefixlen=24)
     .commit())

    (context
     .ndb
     .routes
     .create(dst=ipnet, dst_len=24, gateway=gateway, table=table)
     .commit())

    assert route_exists(context.netns, dst=ipnet, table=table)
    r1 = context.ndb.routes.get('%s/24' % ipnet)
    r2 = context.ndb.routes.get({'dst': '%s/24' % ipnet})
    r3 = context.ndb.routes.get({'dst': ipnet, 'dst_len': 24})
    r4 = context.ndb.routes['%s/24' % ipnet]
    r5 = context.ndb.routes[{'dst': '%s/24' % ipnet}]
    r6 = context.ndb.routes[{'dst': ipnet, 'dst_len': 24}]
    assert r1 == r2 == r3 == r4 == r5 == r6


def test_string_key_in_interfaces(context):

    ifname = context.new_ifname
    address = '00:11:22:33:44:55'
    f_ifname = context.new_ifname
    f_address = '00:11:22:33:66:66'

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up', address=address)
     .commit())

    assert ifname in context.ndb.interfaces
    assert address in context.ndb.interfaces
    assert f_ifname not in context.ndb.interfaces
    assert f_address not in context.ndb.interfaces


def test_string_key_in_addresses(context):

    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    f_ipaddr = context.new_ipaddr

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .add_ip(address=ipaddr, prefixlen=24)
     .commit())

    assert ipaddr in context.ndb.addresses
    assert '%s/%i' % (ipaddr, 24) in context.ndb.addresses
    assert f_ipaddr not in context.ndb.addresses
    assert '%s/%i' % (f_ipaddr, 24) not in context.ndb.addresses
    assert '%s/%i' % (ipaddr, 16) not in context.ndb.addresses
    assert '%s/%i' % (ipaddr, 28) not in context.ndb.addresses
    assert '%s/%i' % (ipaddr, 32) not in context.ndb.addresses
