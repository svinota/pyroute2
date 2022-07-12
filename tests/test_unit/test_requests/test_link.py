import pytest
from common import Request, Result, run_test

from pyroute2.requests.link import LinkFieldFilter, LinkIPRouteFilter

config_add = {
    'filters': (
        {'class': LinkFieldFilter, 'argv': []},
        {'class': LinkIPRouteFilter, 'argv': ['add']},
    )
}
config_dump = {
    'filters': (
        {'class': LinkFieldFilter, 'argv': []},
        {'class': LinkIPRouteFilter, 'argv': ['dump']},
    )
}

result_add = Result(
    {
        'index': 1,
        'change': 0,
        'flags': 0,
        'IFLA_LINKINFO': {'attrs': [['IFLA_INFO_KIND', 'dummy']]},
    }
)
result_dump = Result({'index': 1, ('linkinfo', 'kind'): 'dummy'})


@pytest.mark.parametrize(
    'config,spec,result',
    (
        (config_add, Request({'index': 1, 'kind': 'dummy'}), result_add),
        (config_add, Request({'index': [1], 'kind': 'dummy'}), result_add),
        (config_add, Request({'index': (1,), 'kind': 'dummy'}), result_add),
        (config_dump, Request({'index': 1, 'kind': 'dummy'}), result_dump),
        (config_dump, Request({'index': [1], 'kind': 'dummy'}), result_dump),
        (config_dump, Request({'index': (1,), 'kind': 'dummy'}), result_dump),
    ),
    ids=[
        'int-add',
        'list-add',
        'tuple-add',
        'int-dump',
        'list-dump',
        'tuple-dump',
    ],
)
def test_index(config, spec, result):
    return run_test(config, spec, result)


@pytest.mark.parametrize(
    'spec,result',
    (
        (
            Request({'kind': 'bridge', 'br_stp_state': 1}),
            Result(
                {
                    ('linkinfo', 'kind'): 'bridge',
                    ('linkinfo', 'data', 'br_stp_state'): 1,
                }
            ),
        ),
        (
            Request({'kind': 'bond', 'bond_primary': 1}),
            Result(
                {
                    ('linkinfo', 'kind'): 'bond',
                    ('linkinfo', 'data', 'bond_primary'): 1,
                }
            ),
        ),
        (
            Request({'kind': 'vxlan', 'vxlan_id': 1}),
            Result(
                {
                    ('linkinfo', 'kind'): 'vxlan',
                    ('linkinfo', 'data', 'vxlan_id'): 1,
                }
            ),
        ),
        (
            Request({'kind': 'fake', 'fake_attr': 1}),
            Result({('linkinfo', 'kind'): 'fake', 'fake_attr': 1}),
        ),
    ),
    ids=['bridge', 'bond', 'vxlan', 'fake'],
)
def test_dump_specific(spec, result):
    return run_test(config_dump, spec, result)
