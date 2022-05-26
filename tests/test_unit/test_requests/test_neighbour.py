from socket import AF_INET

import pytest
from common import Request, Result, run_test
from pr2modules.netlink.rtnl.ndmsg import NUD_PERMANENT
from pr2modules.requests.neighbour import (
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
    ),
    ids=['int', 'list', 'tuple'],
)
def test_index(spec, result):
    return run_test(config, spec, result)
