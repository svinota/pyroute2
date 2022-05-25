from socket import AF_INET, AF_INET6

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
        (
            {
                'index': 1,
                'address': '10.0.0.1',
                'prefixlen': 28,
                'broadcast': '10.0.0.15',
            },
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'prefixlen': 28,
                'broadcast': '10.0.0.15',
                'family': AF_INET,
            },
        ),
    ),
    ids=('bool-true', 'bool-false', 'ipv4'),
)
def test_add_broadcast(spec, result):
    return _test(spec, result)


##
#
# index format tests: int, list, tuple
#
result = {
    'index': 1,
    'address': '10.0.0.1',
    'local': '10.0.0.1',
    'prefixlen': 24,
    'family': AF_INET,
}


@pytest.mark.parametrize(
    'spec,result',
    (
        ({'index': 1, 'address': '10.0.0.1', 'prefixlen': 24}, result),
        ({'index': [1], 'address': '10.0.0.1', 'prefixlen': 24}, result),
        ({'index': (1,), 'address': '10.0.0.1', 'prefixlen': 24}, result),
    ),
    ids=('int', 'list', 'tuple'),
)
def test_index(spec, result):
    return _test(spec, result)


@pytest.mark.parametrize(
    'spec,result',
    (
        (
            {'index': 1, 'address': '10.0.0.1'},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'family': AF_INET,
                'prefixlen': 32,
            },
        ),
        (
            {'index': 1, 'address': '10.0.0.1', 'prefixlen': 16},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'family': AF_INET,
                'prefixlen': 16,
            },
        ),
        (
            {'index': 1, 'address': '10.0.0.1/24'},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'family': AF_INET,
                'prefixlen': 24,
            },
        ),
        (
            {'index': 1, 'address': '10.0.0.1', 'prefixlen': '255.0.0.0'},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'family': AF_INET,
                'prefixlen': 8,
            },
        ),
        (
            {'index': 1, 'address': '10.0.0.1/255.255.255.240'},
            {
                'index': 1,
                'address': '10.0.0.1',
                'local': '10.0.0.1',
                'family': AF_INET,
                'prefixlen': 28,
            },
        ),
        (
            {'index': 1, 'address': 'fc00::1'},
            {
                'index': 1,
                'address': 'fc00::1',
                'family': AF_INET6,
                'prefixlen': 128,
            },
        ),
        (
            {'index': 1, 'address': 'fc00::1', 'prefixlen': 64},
            {
                'index': 1,
                'address': 'fc00::1',
                'family': AF_INET6,
                'prefixlen': 64,
            },
        ),
        (
            {'index': 1, 'address': 'fc00::1/48'},
            {
                'index': 1,
                'address': 'fc00::1',
                'family': AF_INET6,
                'prefixlen': 48,
            },
        ),
        (
            {
                'index': 1,
                'address': 'fc00:0000:0000:0000:0000:0000:0000:0001/32',
            },
            {
                'index': 1,
                'address': 'fc00::1',
                'family': AF_INET6,
                'prefixlen': 32,
            },
        ),
    ),
    ids=(
        'ipv4-default',
        'ipv4-prefixlen',
        'ipv4-split',
        'ipv4-prefixlen-dqn',
        'ipv4-split-dqn',
        'ipv6-default',
        'ipv6-prefixlen',
        'ipv6-split',
        'ipv6-compressed',
    ),
)
def test_family_and_prefix(spec, result):
    return _test(spec, result)
