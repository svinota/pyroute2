import re

from net_tools import address_exists

ip4v6 = re.compile('^[.:0-9a-f]*$')


def test_addr_dump(sync_ipr):
    for addr in sync_ipr.addr('dump'):
        index = addr.get('index')
        address = addr.get('address', '')
        prefixlen = addr.get('prefixlen')
        assert index > 0
        assert ip4v6.match(address)
        assert prefixlen > 0


def test_addr_add(sync_ipr, ifname, index, nsname):
    sync_ipr.addr('add', index=index, address='192.168.145.150', prefixlen=24)
    assert address_exists('192.168.145.150', ifname, netns=nsname)
