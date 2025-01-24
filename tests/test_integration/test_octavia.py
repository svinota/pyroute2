from net_tools import interface_exists

import pyroute2
from pyroute2.common import uifname


def test_amphora_info(nsname):
    with pyroute2.NetNS(netns=nsname) as ns:
        for interface in ns.get_links():
            for item in interface['attrs']:
                if item[0] == 'IFLA_IFNAME':
                    assert isinstance(item[1], str)
                if item[0] == 'IFLA_STATS64':
                    assert isinstance(item[1]['tx_bytes'], int)
                    assert isinstance(item[1]['rx_bytes'], int)


def test_api_server_plug(nsname, link):
    newname = uifname()
    with pyroute2.IPRoute(netns=link.netns) as ipr:
        idx = ipr.link_lookup(address=link.get('address'))[0]
        ipr.link('set', index=idx, net_ns_fd=nsname, IFLA_IFNAME=newname)
    assert not interface_exists(
        ifname=link.get('ifname'), netns=link.netns, timeout=0.1
    )
    assert interface_exists(ifname=newname, netns=nsname)


def test_api_server_mac(link):
    with pyroute2.IPRoute(netns=link.netns) as ipr:
        idx = ipr.link_lookup(address=link.get('address'))[0]
        addr = ipr.get_links(idx)[0]
        for attr in addr['attrs']:
            if attr[0] == 'IFLA_IFNAME':
                assert attr[1] == link.get('ifname')


def test_api_server_attrs(link):
    attr_dict = dict(link['attrs'])
    assert attr_dict.get('IFLA_ADDRESS') == link.get('address')
    assert attr_dict.get('IFLA_IFNAME') == link.get('ifname')
