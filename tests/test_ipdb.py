from pyroute2 import ipdb


class TestSetup(object):
    ip = None

    def setup(self):
        self.ip = ipdb()

    def teardown(self):
        self.ip.shutdown()

    def test_simple(self):
        assert self.ip.keys() > 0

    def test_idx_len(self):
        assert len(self.ip.by_name.keys()) == len(self.ip.by_index.keys())

    def test_idx_set(self):
        assert set(self.ip.by_name.values()) == set(self.ip.by_index.values())

    def test_idx_types(self):
        assert all(isinstance(i, int) for i in self.ip.by_index.keys())
        assert all(isinstance(i, basestring) for i in self.ip.by_name.keys())
