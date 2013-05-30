from pyroute2 import IPDB
# tests imports
from utils import get_ip_addr


class TestBasic(object):
    ip = None

    def setup(self):
        self.ip = IPDB()

    def teardown(self):
        self.ip.release()

    def test_simple(self):
        assert self.ip.keys() > 0

    def test_idx_len(self):
        assert len(self.ip.by_name.keys()) == len(self.ip.by_index.keys())

    def test_idx_set(self):
        assert set(self.ip.by_name.values()) == set(self.ip.by_index.values())

    def test_idx_types(self):
        assert all(isinstance(i, int) for i in self.ip.by_index.keys())
        assert all(isinstance(i, basestring) for i in self.ip.by_name.keys())

    def test_ips(self):
        for name in self.ip.by_name:
            assert len(self.ip[name]['ipaddr']) == len(get_ip_addr(name))
