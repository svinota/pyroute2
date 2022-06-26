import errno

from nose.plugins.skip import SkipTest

from pyroute2 import DL
from pyroute2.netlink.exceptions import NetlinkError


class TestDL(object):
    def setup(self):
        try:
            self.dl = DL()
        except NetlinkError as e:
            if e.code == errno.ENOENT:
                raise SkipTest('devlink not supported')
            else:
                raise
        dls = self.dl.get_dump()
        if not dls:
            raise SkipTest('no devlink devices found')

    def teardown(self):
        self.dl.close()

    def test_list(self):
        self.dl.list()
