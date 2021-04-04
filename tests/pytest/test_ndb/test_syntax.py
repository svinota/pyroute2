from pr2test.tools import interface_exists
from pr2test.tools import address_exists


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
