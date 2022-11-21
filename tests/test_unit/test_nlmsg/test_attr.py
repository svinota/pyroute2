import pytest

from pyroute2.netlink import nlmsg

prime = {
    'attrs': (
        ('A', 2),
        ('A', 3),
        ('A', 4),
        ('B', {'attrs': (('C', 5), ('D', {'attrs': (('E', 6), ('F', 7))}))}),
    )
}


@pytest.fixture
def msg():
    msg = nlmsg()
    msg.setvalue(prime)
    yield msg


def test_get_attr(msg):
    assert msg.get_attr('A') == 2
    assert msg.get_attr('C') is None


def test_get_attrs(msg):
    assert msg.get_attrs('A') == [2, 3, 4]
    assert msg.get_attrs('C') == []


def test_get_nested(msg):
    assert msg.get_nested('B', 'D', 'E') == 6
    assert msg.get_nested('B', 'D', 'F') == 7
    assert msg.get_nested('B', 'D', 'G') is None
    assert msg.get_nested('C', 'D', 'E') is None
