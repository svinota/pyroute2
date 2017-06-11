import errno
from utils import require_user
from pyroute2 import IW
from pyroute2 import IPRoute
from pyroute2.netlink.exceptions import NetlinkError
from nose.plugins.skip import SkipTest


class TestIW(object):

    def setup(self):
        try:
            self.iw = IW()
        except NetlinkError as e:
            if e.code == errno.ENOENT:
                raise SkipTest('nl80211 not supported')
            else:
                raise
        ifaces = self.iw.get_interfaces_dump()
        if not ifaces:
            raise SkipTest('no wireless interfaces found')
        for i in ifaces:
            self.ifname = i.get_attr('NL80211_ATTR_IFNAME')
            self.ifindex = i.get_attr('NL80211_ATTR_IFINDEX')
            self.wiphy = i.get_attr('NL80211_ATTR_WIPHY')
            if self.ifindex:
                return
        raise Exception('can not detect the interface to use')

    def teardown(self):
        self.iw.close()

    def test_list_wiphy(self):
        self.iw.list_wiphy()

    def test_list_dev(self):
        self.iw.list_dev()

    def test_scan(self):
        require_user('root')
        with IPRoute() as ipr:
            ipr.link('set', index=self.ifindex, state='up')
        self.iw.scan(self.ifindex)
