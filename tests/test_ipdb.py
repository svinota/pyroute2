from pyroute2 import IPDB
from utils import setup_dummy
from utils import remove_link
from utils import remove_dummy
from utils import require_user
from utils import get_ip_addr


class TestBasic(object):
    ip = None

    def setup(self):
        setup_dummy()
        self.ip = IPDB()

    def teardown(self):
        self.ip.release()
        remove_dummy()

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

    def test_create_plain(self):
        require_user('root')
        assert 'bala' not in self.ip
        i = self.ip.create(kind='dummy', ifname='bala')
        i.add_ip('172.16.14.1/24')
        i.commit()
        assert '172.16.14.1/24' in get_ip_addr(interface='bala')
        remove_link('bala')

    def test_create_cm(self):
        require_user('root')
        assert 'bala' not in self.ip
        with self.ip.create(kind='dummy', ifname='bala') as i:
            i.add_ip('172.16.14.1/24')
        assert '172.16.14.1/24' in get_ip_addr(interface='bala')
        remove_link('bala')

    def test_create_bond(self):
        require_user('root')
        assert 'bala' not in self.ip
        assert 'bala_port0' not in self.ip
        assert 'bala_port1' not in self.ip

        self.ip.create(kind='dummy', ifname='bala_port0').commit()
        self.ip.create(kind='dummy', ifname='bala_port1').commit()

        with self.ip.create(kind='bond', ifname='bala') as i:
            i.add_port(self.ip.bala_port0)
            i.add_port(self.ip.bala_port1)
            i.add_ip('172.16.15.1/24')

        self.ip._links_event.wait()
        assert '172.16.15.1/24' in get_ip_addr(interface='bala')
        assert self.ip.bala_port0.if_master == self.ip.bala
        assert self.ip.bala_port1.if_master == self.ip.bala

        remove_link('bala_port0')
        remove_link('bala_port1')
        remove_link('bala')
