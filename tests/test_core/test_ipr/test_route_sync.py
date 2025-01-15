import pytest

from pyroute2 import IPRoute


@pytest.mark.parametrize(
    "command,kwarg",
    [
        ("dump", {"table": 255}),
        ("show", {"table": 255}),
        ("dump", {"match": {"table": 255}}),
        ("show", {"match": {"table": 255}}),
    ],
)
def test_route_filter(sync_ipr, command, kwarg):
    assert set(
        [route.get('table') for route in sync_ipr.route(command, **kwarg)]
    ) == set([255])


@pytest.mark.parametrize(
    "command,kwarg",
    [
        ("dump", {"table": 255, "family": 1}),
        ("show", {"table": 255, "family": 1}),
    ],
)
def test_route_filter_strict(command, kwarg):
    with IPRoute(strict_check=True) as ipr:
        assert set(
            [route.get('table') for route in ipr.route(command, **kwarg)]
        ) == set([255])
