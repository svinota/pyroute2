import pytest
from net_tools import interface_exists

import pyroute2
from pyroute2 import IPDB
from pyroute2.common import uifname
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

# from pyroute2.common import uifname
TADDR = '00:11:22:33:44:55'
KIND = 'ipvlan'
IPVLAN_MODE_L2 = ifinfmsg.ifinfo.data_map['ipvlan'].modes['IPVLAN_MODE_L2']


@pytest.fixture
def ipdb(link):
    with IPDB(sources=[{'target': 'localhost', 'netns': link.netns}]) as ip:
        yield ip


@pytest.mark.parametrize(
    'exc',
    (
        pyroute2.NetlinkError,
        pyroute2.CreateException,
        pyroute2.CommitException,
    ),
)
def test_exception_types(exc):
    assert issubclass(exc, Exception)


def test_ipdb_create_exception(link, ipdb):
    with pytest.raises(pyroute2.CreateException):
        ipdb.create(ifname=link.get('ifname'), kind='dummy').commit()


def test_ipdb_create_reuse(link, ipdb):
    ipdb.create(ifname=link.get('ifname'), kind='dummy', reuse=True).commit()


@pytest.mark.parametrize(
    'method,argv,check',
    (
        ('set_mtu', [1000], lambda x: x['mtu'] == 1000),
        ('set_address', [TADDR], lambda x: x['address'] == TADDR),
        ('add_ip', ['10.1.2.3', 24], lambda x: '10.1.2.3/24' in x.ipaddr),
        ('up', [], lambda x: x['flags'] & 1),
    ),
)
def test_ipdb_iface_methods(link, ipdb, method, argv, check):
    iface = ipdb.interfaces[link.get('ifname')]
    with iface:
        getattr(iface, method)(*argv)
    assert check(iface)


def test_utils_remove(link, ifname, ipdb):
    index = ipdb.interfaces.get(ifname, {}).get('index', None)
    assert isinstance(index, int)
    with ipdb.interfaces[ifname] as iface:
        iface.remove()
    assert ifname not in ipdb.interfaces
    assert not interface_exists(ifname, link.netns, timeout=0.1)


def test_get_iface(link, ifname, ipdb):
    with ipdb.interfaces[ifname] as link:
        link.set_address(TADDR)
    target = None
    for name, data in ipdb.interfaces.items():
        if data['address'] == TADDR:
            target = data['ifname']
    assert target == ifname


def test_create_ipvlan(link, ifname, ipdb):
    ipvlname = uifname()
    with ipdb.create(
        ifname=ipvlname,
        kind=KIND,
        link=ipdb.interfaces[ifname],
        ipvlan_mode=IPVLAN_MODE_L2,
    ) as iface:
        assert iface['mode'] == IPVLAN_MODE_L2
        assert iface['ifname'] == ipvlname
        assert iface['link'] == link.get('index')
        assert iface['kind'] == KIND
