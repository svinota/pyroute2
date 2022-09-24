import pytest

from pyroute2 import IPRoute


@pytest.fixture
def ipr():
    with IPRoute() as iproute:
        yield iproute


@pytest.mark.parametrize('variant', ('links', 'addr', 'neighbours', 'routes'))
def test_list(ipr, variant):
    for msg in getattr(ipr, f'get_{variant}')():
        assert msg['header']['target'] == 'localhost'
        assert msg['header']['type'] % 2 == 0
