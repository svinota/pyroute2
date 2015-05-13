from pyroute2 import IW
from nose.plugins.skip import SkipTest


class TestIW(object):

    def setup(self):
        self.iw = IW()
        ifaces = self.iw.get_interfaces_dump()
        if not ifaces:
            raise SkipTest('no wireless interfaces found')
        self.ifname = ifaces[0].get_attr('NL80211_ATTR_IFNAME')
        self.ifindex = ifaces[0].get_attr('NL80211_ATTR_IFINDEX')
        self.wiphy = ifaces[0].get_attr('NL80211_ATTR_WIPHY')

    def teardown(self):
        self.iw.close()

    def test_list_wiphy(self):
        self.iw.list_wiphy()

    def test_list_dev(self):
        self.iw.list_dev()

    def test_scan(self):
        self.iw.scan(self.ifindex)
