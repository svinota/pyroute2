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
    with pyroute2.IPRoute() as ipr:
        idx = ipr.link_lookup(address=link.get('address'))[0]
        ipr.link('set', index=idx, net_ns_fd=nsname, IFLA_IFNAME=newname)
    assert interface_exists(ifname=newname, netns=nsname)
