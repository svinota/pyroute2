from socket import AF_INET

import pytest
from pr2modules.requests.address import (
    AddressFieldFilter,
    AddressIPRouteFilter,
)
from pr2modules.requests.main import RequestProcessor


def _test(spec, result):
    request = (
        RequestProcessor(context=spec, prime=spec)
        .apply_filter(AddressFieldFilter())
        .apply_filter(AddressIPRouteFilter('add'))
        .finalize()
    )
    assert dict(request) == result


##
#
# broadcast tests: bool
#
@pytest.mark.parametrize(
    'spec,result',
    (
        (
            {
                'index': 1,
                'address': '10.0.0.1',
                'prefixlen': 24,
                'broadcast': True,
            },
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'prefixlen': 24,
                'broadcast': '10.0.0.255',
                'family': AF_INET,
            },
        ),
        (
            {
                'index': 1,
                'address': '10.0.0.1',
                'prefixlen': 24,
                'broadcast': False,
            },
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'prefixlen': 24,
                'family': AF_INET,
            },
        ),
    ),
)
def test_add_broadcast(spec, result):
    return _test(spec, result)


##
#
# index format tests: int, list, tuple
#
@pytest.mark.parametrize(
    'spec,result',
    (
        (
            {'index': 1, 'address': '10.0.0.1', 'prefixlen': 24},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'prefixlen': 24,
                'family': AF_INET,
            },
        ),
        (
            {'index': [1], 'address': '10.0.0.1', 'prefixlen': 24},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'prefixlen': 24,
                'family': AF_INET,
            },
        ),
        (
            {'index': (1,), 'address': '10.0.0.1', 'prefixlen': 24},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'prefixlen': 24,
                'family': AF_INET,
            },
        ),
    ),
)
def test_index(spec, result):
    return _test(spec, result)
