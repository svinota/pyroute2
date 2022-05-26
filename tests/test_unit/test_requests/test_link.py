import pytest
from common import Request, Result, run_test
from pr2modules.requests.link import LinkFieldFilter, LinkIPRouteFilter

config = {
    'filters': (
        {'class': LinkFieldFilter, 'argv': []},
        {'class': LinkIPRouteFilter, 'argv': ['add']},
    )
}


result = Result(
    {
        'index': 1,
        'change': 0,
        'flags': 0,
        'IFLA_LINKINFO': {'attrs': [['IFLA_INFO_KIND', 'dummy']]},
    }
)


@pytest.mark.parametrize(
    'spec,result',
    (
        (Request({'index': 1, 'kind': 'dummy'}), result),
        (Request({'index': [1], 'kind': 'dummy'}), result),
        (Request({'index': (1,), 'kind': 'dummy'}), result),
    ),
    ids=['int', 'list', 'tuple'],
)
def test_index(spec, result):
    return run_test(config, spec, result)
