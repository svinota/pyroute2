import json

import pytest

from pyroute2 import IPRoute
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.requests.link import LinkFieldFilter, LinkIPRouteFilter
from pyroute2.requests.main import RequestProcessor

with open('test_unit/test_iproute_match/links.dump', 'r') as f:
    ifinfmsg_sample = [ifinfmsg().load(x) for x in json.load(f)]
for msg in ifinfmsg_sample:
    msg.reset()
    msg.encode()
    msg.decode()


@pytest.fixture
def ipr():
    with IPRoute() as iproute:
        yield iproute


@pytest.mark.parametrize(
    'spec,query,result',
    (
        ({'ifname': 'lo'}, ('stats64', 'rx_packets'), 120),
        ({'ifname': 'lo'}, ('af_spec', 'af_inet', 'forwarding'), 1),
        ({'ifname': 'wl0'}, ('num_rx_queues',), 1),
        ({'ifname': 'wl0'}, ('qdisc',), 'noqueue'),
        ({'ifname': 'wl0'}, ('stats64', 'rx_packets'), 835511),
        (
            {'ifname': 'wl0'},
            ('af_spec', 'af_inet6', 'inet6_flags'),
            2147483648,
        ),
        (
            {'ifname': 'wl0'},
            ('af_spec', 'af_inet6', 'inet6_conf', 'temp_preferred_lft'),
            86400,
        ),
        ({'parent_dev_name': '0000:03:00.0'}, ('ifname',), 'wl0'),
        ({'kind': 'bridge', 'br_forward_delay': 1500}, ('ifname',), 'br0'),
        (
            {'ifname': 'br0'},
            ('linkinfo', 'data', 'br_group_addr'),
            '01:80:c2:00:00:00',
        ),
    ),
    ids=[
        'lo:stats64/rx_packets',
        'lo:af_spec/af_inet/forwarding',
        'wl0:num_rx_queues',
        'wl0:qdisc',
        'wl0:stats64/rx_packets',
        'wl0:af_spec/af_inet6/inet6_flags',
        'wl0:af_spec/af_inet6/inet6_conf/temp_preferred_lft',
        'parent_dev_name(...) => wl0',
        'br_forward_delay(...) => br0',
        'br0:linkinfo/data/br_group_addr',
    ],
)
def test_get_leaf(ipr, spec, query, result):
    spec = RequestProcessor(context=spec, prime=spec)
    spec.apply_filter(LinkFieldFilter())
    spec.apply_filter(LinkIPRouteFilter('dump'))
    spec.finalize()

    msg = ipr.filter_messages(spec, ifinfmsg_sample)
    assert len(msg) == 1
    assert msg[0].get_nested(*query) == result
