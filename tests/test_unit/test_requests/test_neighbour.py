from socket import AF_INET, AF_INET6

import pytest
from common import Request, Result, run_test

from pyroute2.netlink.rtnl.ndmsg import NUD_FAILED, NUD_PERMANENT
from pyroute2.requests.neighbour import (
    NeighbourFieldFilter,
    NeighbourIPRouteFilter,
)

config = {
    'filters': (
        {'class': NeighbourFieldFilter, 'argv': []},
        {'class': NeighbourIPRouteFilter, 'argv': ['add']},
    )
}


result = Result({'ifindex': 1, 'family': AF_INET, 'state': NUD_PERMANENT})


@pytest.mark.parametrize(
    'spec,result',
    (
        (Request({'index': 1}), result),
        (Request({'index': [1]}), result),
        (Request({'index': (1,)}), result),
        (Request({'ifindex': 1}), result),
        (Request({'ifindex': [1]}), result),
        (Request({'ifindex': (1,)}), result),
    ),
    ids=['ix-int', 'ix-list', 'ix-tuple', 'ifx-int', 'ifx-list', 'ifx-tuple'],
)
def test_index(spec, result):
    return run_test(config, spec, result)


@pytest.mark.parametrize(
    'spec,result',
    (
        (
            Request({'ifindex': 1, 'dst': '10.0.0.1'}),
            Result(
                {
                    'ifindex': 1,
                    'dst': '10.0.0.1',
                    'family': AF_INET,
                    'state': NUD_PERMANENT,
                }
            ),
        ),
        (
            Request({'ifindex': 1, 'dst': 'fc00::1'}),
            Result(
                {
                    'ifindex': 1,
                    'dst': 'fc00::1',
                    'family': AF_INET6,
                    'state': NUD_PERMANENT,
                }
            ),
        ),
    ),
    ids=['ipv4', 'ipv6'],
)
def test_family(spec, result):
    return run_test(config, spec, result)


@pytest.mark.parametrize(
    'spec,result',
    (
        (
            Request({'ifindex': 1, 'state': 'permanent'}),
            Result({'ifindex': 1, 'state': NUD_PERMANENT, 'family': AF_INET}),
        ),
        (
            Request({'ifindex': 1, 'state': 'failed'}),
            Result({'ifindex': 1, 'state': NUD_FAILED, 'family': AF_INET}),
        ),
        (
            Request({'ifindex': 1, 'nud': 'permanent'}),
            Result({'ifindex': 1, 'state': NUD_PERMANENT, 'family': AF_INET}),
        ),
        (
            Request({'ifindex': 1, 'nud': 'failed'}),
            Result({'ifindex': 1, 'state': NUD_FAILED, 'family': AF_INET}),
        ),
        (
            Request({'ifindex': 1, 'nud': NUD_PERMANENT}),
            Result({'ifindex': 1, 'state': NUD_PERMANENT, 'family': AF_INET}),
        ),
        (
            Request({'ifindex': 1, 'nud': NUD_FAILED}),
            Result({'ifindex': 1, 'state': NUD_FAILED, 'family': AF_INET}),
        ),
    ),
    ids=[
        'str-permanent',
        'str-failed',
        'nud-permanent',
        'nud-failed',
        'const-permanent',
        'const-failed',
    ],
)
def test_state(spec, result):
    return run_test(config, spec, result)
