import collections
import errno

import pytest
from pr2test.marks import require_root

from pyroute2 import IW, IPRoute
from pyroute2.netlink.exceptions import NetlinkError


@pytest.fixture
def ctx():
    iw = None
    ifname = None
    wiphy = None
    index = None
    try:
        iw = IW()
    except NetlinkError as e:
        if e.code == errno.ENOENT:
            pytest.skip('nl80211 not supported')
        raise
    ifaces = iw.get_interfaces_dump()
    if not ifaces:
        raise pytest.skip('no wireless interfaces found')
    for i in ifaces:
        ifname = i.get_attr('NL80211_ATTR_IFNAME')
        index = i.get_attr('NL80211_ATTR_IFINDEX')
        wiphy = i.get_attr('NL80211_ATTR_WIPHY')
        if index:
            break
    else:
        pytest.skip('can not detect the interface to use')

    yield collections.namedtuple(
        'WirelessContext', ['iw', 'ifname', 'index', 'wiphy']
    )(iw, ifname, index, wiphy)

    iw.close()


def test_list_wiphy(ctx):
    ctx.iw.list_wiphy()


def test_list_dev(ctx):
    ctx.iw.list_dev()


@require_root
def test_scan(ctx):
    with IPRoute() as ipr:
        ipr.link('set', index=ctx.index, state='up')
    ctx.iw.scan(ctx.index)
