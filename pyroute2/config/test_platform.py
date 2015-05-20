'''
A set of platform tests to discover the system capabilities
'''
from pyroute2.common import uifname
from pyroute2 import RawIPRoute


class TestCapsRtnl(object):

    def __init__(self):
        self.capabilities = {}
        self.ifnames = [uifname() for _ in range(10)]

    def __getitem__(self, key):
        return self.capabilities[key]

    def set_capability(self, key, value):
        self.capabilities[key] = value

    def setup(self):
        self.ip = RawIPRoute()

    def teardown(self):
        for ifname in self.ifnames:
            idx = self.ip.link_lookup(ifname=ifname)
            if idx:
                self.ip.link_remove(idx[0])
        self.ip.close()

    def collect(self):
        symbols = dir(self)
        for name in symbols:
            if name.startswith('test_'):
                self.setup()
                try:
                    ret = getattr(self, name)()
                    if ret is None:
                        ret = True
                    self.set_capability(name[5:], ret)
                except Exception:
                    self.set_capability(name[5:], False)
                self.teardown()

    def test_create_bridge(self):
        self.ip.link_create(ifname=self.ifnames[0], kind='bridge')

    def test_create_bond(self):
        self.ip.link_create(ifname=self.ifnames[0], kind='bond')
