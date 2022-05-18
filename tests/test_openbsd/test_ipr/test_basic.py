from pr2modules.common import get_address_family
from pr2modules.netlink.rtnl import (
    RTM_NEWADDR,
    RTM_NEWLINK,
    RTM_NEWNEIGH,
    RTM_NEWROUTE,
)


def test_get_links(context):
    for msg in context.ipr.get_links():
        assert msg['header']['target'] == 'localhost'
        assert msg['header']['type'] == RTM_NEWLINK
        #
        assert msg['index'] > 0
        ifname = msg.get_attr('IFLA_IFNAME')
        assert isinstance(ifname, str)


def test_get_addr(context):
    for msg in context.ipr.get_addr():
        assert msg['header']['target'] == 'localhost'
        assert msg['header']['type'] == RTM_NEWADDR
        #
        addr = msg.get_attr('IFA_ADDRESS')
        assert isinstance(addr, str)
        assert msg['family'] == get_address_family(addr)
        assert 0 <= msg['prefixlen'] <= 128


def test_get_routes(context):
    for msg in context.ipr.get_routes():
        assert msg['header']['target'] == 'localhost'
        assert msg['header']['type'] == RTM_NEWROUTE


def test_get_neighbours(context):
    for msg in context.ipr.get_neighbours():
        assert msg['header']['target'] == 'localhost'
        assert msg['header']['type'] == RTM_NEWNEIGH
        #
        dst = msg.get_attr('NDA_DST')
        lladdr = msg.get_attr('NDA_LLADDR')
        assert msg['family'] == get_address_family(dst)
        assert isinstance(lladdr, str)
        assert len(lladdr.split(':')) == 6
