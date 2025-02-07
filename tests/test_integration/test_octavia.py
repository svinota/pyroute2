import errno
import os

import pytest
from net_tools import interface_exists

import pyroute2
from pyroute2.common import uifname
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.rtnl import ifaddrmsg, rt_proto


def test_amphora_info(nsname):
    with pyroute2.NetNS(netns=nsname) as ns:
        for interface in ns.get_links():
            for item in interface['attrs']:
                if item[0] == 'IFLA_IFNAME':
                    assert isinstance(item[1], str)
                if item[0] == 'IFLA_STATS64':
                    assert isinstance(item[1]['tx_bytes'], int)
                    assert isinstance(item[1]['rx_bytes'], int)


def test_api_server_plug(nsname, test_link_ifname, test_link_address):
    newname = uifname()
    with pyroute2.IPRoute(netns=nsname) as ipr:
        idx = ipr.link_lookup(address=test_link_address)[0]
        ipr.link('set', index=idx, net_ns_fd=nsname, IFLA_IFNAME=newname)
    assert not interface_exists(
        ifname=test_link_ifname, netns=nsname, timeout=0.1
    )
    assert interface_exists(ifname=newname, netns=nsname)


def test_api_server_mac(nsname, test_link_address, test_link_ifname):
    with pyroute2.IPRoute(netns=nsname) as ipr:
        idx = ipr.link_lookup(address=test_link_address)[0]
        addr = ipr.get_links(idx)[0]
        for attr in addr['attrs']:
            if attr[0] == 'IFLA_IFNAME':
                assert attr[1] == test_link_ifname


def test_api_server_attrs(
    test_link_ifinfmsg, test_link_address, test_link_ifname
):
    attr_dict = dict(test_link_ifinfmsg['attrs'])
    assert attr_dict.get('IFLA_ADDRESS') == test_link_address
    assert attr_dict.get('IFLA_IFNAME') == test_link_ifname


def test_api_server_netns_flags(nsname):
    with pyroute2.NetNS(nsname, flags=os.O_CREAT) as netns:
        for link in netns.get_links():
            assert isinstance(link.get('address'), str)
            assert isinstance(link.get('ifname'), str)


def test_utils_exception_ref():
    assert pyroute2.NetlinkError is NetlinkError
    e = NetlinkError(errno.EINVAL, 'message')
    assert e.code == errno.EINVAL


def test_utils_link_attr(test_link_ifname, sync_ipr):
    idx = sync_ipr.link_lookup(ifname=test_link_ifname)[0]
    ref = sync_ipr.get_links(idx)[0]
    assert ref.get('state') == 'up'
    sync_ipr.link('set', index=idx, state='down', mtu=1000)
    sync_ipr.poll(
        sync_ipr.link, 'dump', index=idx, state='down', mtu=1000, timeout=5
    )
    with pytest.raises(TimeoutError):
        sync_ipr.poll(
            sync_ipr.link, 'dump', index=idx, state='up', timeout=0.1
        )
    with pytest.raises(TimeoutError):
        sync_ipr.poll(sync_ipr.link, 'dump', index=idx, mtu=1500, timeout=0.1)


def test_utils_addr_flags(test_link_index, test_link_ifname, sync_ipr, ndb):
    with ndb.interfaces[test_link_ifname] as i:
        i.set('state', 'up')
        i.add_ip('10.1.2.3/24')

    for addr in sync_ipr.get_addr(index=test_link_index):
        attrs = dict(addr['attrs'])
        if attrs['IFA_FLAGS'] & ifaddrmsg.IFA_F_PERMANENT:
            break
    else:
        raise NetlinkError(errno.ENOENT, 'no static addresses')


def test_utils_route_proto(ndb, sync_ipr):
    with ndb.interfaces['lo'] as i:
        i.set('state', 'up')
    for route in sync_ipr.get_routes(oif=1):
        assert route['proto'] != rt_proto['static']
