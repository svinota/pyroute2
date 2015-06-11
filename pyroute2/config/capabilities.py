
from pyroute2.config.test_platform import TestCapsRtnl


class Capabilities(dict):

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
        if not self:
            tc = TestCapsRtnl()
            tc.collect()
            self.update(tc.capabilities)
        return dict.__getitem__(self, key)
