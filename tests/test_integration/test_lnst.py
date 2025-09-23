import select

import pytest

from pyroute2 import IPRoute, IPRSocket
from pyroute2.netlink import NLM_F_DUMP, NLM_F_REQUEST
from pyroute2.netlink.rtnl import RTM_GETADDR, RTM_GETLINK


@pytest.mark.parametrize(
    'msg_type,dump_method,field,event',
    [
        (RTM_GETLINK, 'link', 'ifname', 'RTM_NEWLINK'),
        (RTM_GETADDR, 'addr', 'address', 'RTM_NEWADDR'),
    ],
)
def test_interface_manager_dump_link(
    nsname, msg_type, dump_method, field, event
):
    with IPRSocket(netns=nsname) as iprsock, IPRoute(netns=nsname) as ipr:

        # bring up loopback
        ipr.link('set', index=1, state='up')
        ipr.poll(ipr.addr, 'dump', address='127.0.0.1', timeout=1)

        # init dump:
        # InterfaceManager.request_netlink_dump()
        iprsock.put(None, msg_type, msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

        # collect responses:
        # InterfaceManager.pull_netlink_messages_into_queue()
        ret = []
        while True:
            rl, wl, xl = select.select([iprsock], [], [], 0)
            if not len(rl):
                break
            ret.extend(iprsock.get())

        links = [x for x in getattr(ipr, dump_method)('dump')]
        ifnames_ipr = set([x.get(field) for x in links])
        ifnames_iprsock = set(
            [x.get(field) for x in ret if x.get('event') == event]
        )
        assert ifnames_iprsock == ifnames_ipr
