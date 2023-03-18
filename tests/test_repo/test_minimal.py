import pyroute2
from pyroute2 import minimal


def test_modules():
    assert set(minimal.__all__) < set(pyroute2.__all__)
