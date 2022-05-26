import pytest
from common import Request, Result, run_test
from pr2modules.requests.route import RouteFieldFilter, RouteIPRouteFilter

config = {
    'filters': (
        {'class': RouteFieldFilter, 'argv': []},
        {'class': RouteIPRouteFilter, 'argv': ['add']},
    )
}


result = Result({'oif': 1, 'iif': 2})


@pytest.mark.parametrize(
    'spec,result',
    (
        (Request({'oif': 1, 'iif': 2}), result),
        (Request({'oif': [1], 'iif': [2]}), result),
        (Request({'oif': (1,), 'iif': (2,)}), result),
    ),
    ids=['int', 'list', 'tuple'],
)
def test_index(spec, result):
    return run_test(config, spec, result)
