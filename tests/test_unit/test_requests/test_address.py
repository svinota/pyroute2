from socket import AF_INET, AF_INET6

import pytest
from common import Request, Result, run_test

from pyroute2.requests.address import AddressFieldFilter, AddressIPRouteFilter

config = {
    'filters': (
        {'class': AddressFieldFilter, 'argv': []},
        {'class': AddressIPRouteFilter, 'argv': ['add']},
    )
}


##
#
# broadcast tests: bool
#
@pytest.mark.parametrize(
    'spec,result',
    (
        (
            Request(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'prefixlen': 24,
                    'broadcast': True,
                }
            ),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'prefixlen': 24,
                    'broadcast': '10.0.0.255',
                    'family': AF_INET,
                }
            ),
        ),
        (
            Request(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'prefixlen': 24,
                    'broadcast': False,
                }
            ),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'prefixlen': 24,
                    'family': AF_INET,
                }
            ),
        ),
        (
            Request(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'prefixlen': 28,
                    'broadcast': '10.0.0.15',
                }
            ),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'prefixlen': 28,
                    'broadcast': '10.0.0.15',
                    'family': AF_INET,
                }
            ),
        ),
    ),
    ids=('bool-true', 'bool-false', 'ipv4'),
)
def test_add_broadcast(spec, result):
    return run_test(config, spec, result)


##
#
# index format tests: int, list, tuple
#
result = Result(
    {
        'index': 1,
        'address': '10.0.0.1',
        'local': '10.0.0.1',
        'prefixlen': 24,
        'family': AF_INET,
    }
)


@pytest.mark.parametrize(
    'spec,result',
    (
        (
            Request({'index': 1, 'address': '10.0.0.1', 'prefixlen': 24}),
            result,
        ),
        (
            Request({'index': [1], 'address': '10.0.0.1', 'prefixlen': 24}),
            result,
        ),
        (
            Request({'index': (1,), 'address': '10.0.0.1', 'prefixlen': 24}),
            result,
        ),
    ),
    ids=('int', 'list', 'tuple'),
)
def test_index(spec, result):
    return run_test(config, spec, result)


@pytest.mark.parametrize(
    'spec,result',
    (
        (
            Request({'index': 1, 'address': '10.0.0.1'}),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'family': AF_INET,
                    'prefixlen': 32,
                }
            ),
        ),
        (
            Request({'index': 1, 'address': '10.0.0.1', 'prefixlen': 16}),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'family': AF_INET,
                    'prefixlen': 16,
                }
            ),
        ),
        (
            Request({'index': 1, 'address': '10.0.0.1/24'}),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'family': AF_INET,
                    'prefixlen': 24,
                }
            ),
        ),
        (
            Request(
                {'index': 1, 'address': '10.0.0.1', 'prefixlen': '255.0.0.0'}
            ),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'family': AF_INET,
                    'prefixlen': 8,
                }
            ),
        ),
        (
            Request({'index': 1, 'address': '10.0.0.1/255.255.255.240'}),
            Result(
                {
                    'index': 1,
                    'address': '10.0.0.1',
                    'local': '10.0.0.1',
                    'family': AF_INET,
                    'prefixlen': 28,
                }
            ),
        ),
        (
            Request({'index': 1, 'address': 'fc00::1'}),
            Result(
                {
                    'index': 1,
                    'address': 'fc00::1',
                    'family': AF_INET6,
                    'prefixlen': 128,
                }
            ),
        ),
        (
            Request({'index': 1, 'address': 'fc00::1', 'prefixlen': 64}),
            Result(
                {
                    'index': 1,
                    'address': 'fc00::1',
                    'family': AF_INET6,
                    'prefixlen': 64,
                }
            ),
        ),
        (
            Request({'index': 1, 'address': 'fc00::1/48'}),
            Result(
                {
                    'index': 1,
                    'address': 'fc00::1',
                    'family': AF_INET6,
                    'prefixlen': 48,
                }
            ),
        ),
        (
            Request(
                {
                    'index': 1,
                    'address': 'fc00:0000:0000:0000:0000:0000:0000:0001/32',
                }
            ),
            Result(
                {
                    'index': 1,
                    'address': 'fc00::1',
                    'family': AF_INET6,
                    'prefixlen': 32,
                }
            ),
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
    return run_test(config, spec, result)
