from pyroute2 import IPRoute
from pyroute2 import NetlinkError as E1
from pyroute2.netlink import NetlinkError as E2
from pyroute2.netlink.exceptions import NetlinkError as E3


def test_exceptions():
    assert E1 == E2 == E3
    with IPRoute() as ipr:
        for e in (E1, E2, E3):
            try:
                ipr.get_links(-1)
            except e:
                pass
