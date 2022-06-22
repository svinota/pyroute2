from pyroute2 import IPRoute
from pyroute2.netlink import nlmsg


def test_dump():

    with IPRoute() as ipr:
        assert all([isinstance(message, nlmsg) for message in ipr.dump()])
