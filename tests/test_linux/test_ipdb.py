import pytest

from pyroute2 import IPDB


@pytest.fixture
def ictx(context):
    context.ipdb = IPDB(deprecation_warning=False)
    yield context
    context.ipdb.release()


def test_interface_dummy(ictx):

    ifname = ictx.new_ifname
    ipaddr = ictx.new_ipaddr
    interface = ictx.ipdb.create(ifname=ifname, kind='dummy')
    interface.up()
    interface.add_ip(f'{ipaddr}/24')
    interface.commit()

    ictx.ndb.interfaces.wait(action='add', ifname=ifname, timeout=3)
    assert ictx.ndb.interfaces[ifname]['state'] == 'up'
    assert f'{ipaddr}/24' in ictx.ndb.addresses
    assert (
        ictx.ndb.addresses.wait(action='add', address=ipaddr, prefixlen=24)[
            'index'
        ]
        == interface['index']
    )

    interface.del_ip(f'{ipaddr}/24')
    interface.commit()

    ictx.ndb.addresses.wait(
        action='remove', address=ipaddr, prefixlen=24, timeout=3
    )


def test_interface_veth(ictx):
    netns = ictx.new_nsname
    ictx.ndb.sources.add(netns=netns)
    v0 = ictx.new_ifname
    v1 = ictx.new_ifname

    veth0 = ictx.ipdb.create(ifname=v0, kind='veth', peer=v1)
    veth0.up()
    veth0.commit()

    veth1 = ictx.ipdb.interfaces[v1]
    veth1['net_ns_fd'] = netns
    veth1.commit()

    ictx.ndb.interfaces.wait(ifname=v0, target='localhost', timeout=3)
    ictx.ndb.interfaces.wait(ifname=v1, target=netns, timeout=3)


def test_interface_bridge(ictx):

    ifname = ictx.new_ifname

    with ictx.ipdb.create(ifname=ifname, kind='bridge') as i:
        i.up()
        i['address'] = '00:11:22:33:44:55'
        i['br_stp_state'] = 1
        i['br_forward_delay'] = 1000

    i = ictx.ndb.interfaces.wait(ifname=ifname, timeout=3)
    assert i['state'] == 'up'
    assert i['address'] == '00:11:22:33:44:55'
    assert i['br_stp_state'] == 1
    assert i['br_forward_delay'] == 1000


def test_route_basic(ictx):

    ipaddr = ictx.new_ipaddr
    gateway = ictx.new_ipaddr
    net = ictx.new_ip4net
    ifname = ictx.default_interface.ifname

    with ictx.ipdb.interfaces[ifname] as i:
        i.up()
        i.add_ip(f'{ipaddr}/24')

    ictx.ipdb.routes.add(
        gateway=gateway, dst=f'{net.network}/{net.netmask}'
    ).commit()
