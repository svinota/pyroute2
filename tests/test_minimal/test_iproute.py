import pytest

from pyroute2 import IPRoute
from pyroute2.common import uifname
from pyroute2.netlink import nlmsg


@pytest.fixture
def ipr():
    iproute = IPRoute()
    iproute.default_ifname = uifname()
    yield iproute
    index = iproute.link_lookup(ifname=iproute.default_ifname)
    if index:
        iproute.link('del', index=index)
    iproute.close()


def test_dump(ipr):
    assert all([isinstance(message, nlmsg) for message in ipr.dump()])


def test_tuntap(ipr):
    ipr.link('add', ifname=ipr.default_ifname, kind='tuntap', mode='tun')
    ipr.poll(
        ipr.link, 'dump', timeout=5, ifname=ipr.default_ifname, kind='tun'
    )


def test_bridge(ipr):
    ipr.link('add', ifname=ipr.default_ifname, kind='bridge')
    interface = ipr.poll(
        ipr.link,
        'dump',
        timeout=5,
        ifname=ipr.default_ifname,
        kind='bridge',
        br_stp_state=0,
    )[0]
    ipr.link('set', index=interface['index'], kind='bridge', br_stp_state=1)
    ipr.poll(
        ipr.link,
        'dump',
        timeout=5,
        index=interface['index'],
        kind='bridge',
        br_stp_state=1,
    )
