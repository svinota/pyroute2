from pyroute2 import IPDB
from pyroute2.netlink import NetlinkSocketError
from utils import setup_dummy
from utils import remove_link
from utils import require_user
from utils import get_ip_addr


class TestCM(object):

    def testCM(self):
        with IPDB() as ip:
            assert ip.lo.index == 1


class TestBasic(object):
    ip = None

    def setup(self):
        setup_dummy()
        self.ip = IPDB(mode='implicit')

    def teardown(self):
        self.ip.release()
        remove_link('dummyX')

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

    def test_reprs(self):
        assert isinstance(repr(self.ip.lo.ipaddr), basestring)
        assert isinstance(repr(self.ip.lo), basestring)

    def test_dotkeys(self):
        # self.ip.lo hint for ipython
        assert 'lo' in dir(self.ip)
        # self.ip['lo'] and self.ip.lo
        assert 'lo' in self.ip
        assert self.ip.lo == self.ip['lo']
        # create attribute
        self.ip['newitem'] = True
        self.ip.newattr = True
        self.ip.newitem = None
        assert self.ip.newitem == self.ip['newitem']
        assert self.ip.newitem is None
        # delete attribute
        del self.ip.newitem
        del self.ip.newattr
        assert 'newattr' not in dir(self.ip)

    def test_review(self):
        assert len(self.ip.dummyX._tids) == 0
        self.ip.dummyX.add_ip('172.16.21.1/24')
        r = self.ip.dummyX.review()
        assert len(r['+ipaddr']) == 1
        assert len(r['-ipaddr']) == 0
        assert len(r['+ports']) == 0
        assert len(r['-ports']) == 0
        # flags, +/-ipaddr, +/-ports
        assert len([i for i in r if r[i] is not None]) == 5
        self.ip.dummyX.drop()

    def test_rename(self):
        require_user('root')
        assert 'bala' not in self.ip
        assert 'dummyX' in self.ip

        self.ip.dummyX.ifname = 'bala'
        self.ip.dummyX.commit()

        self.ip._links_event.wait()
        assert 'bala' in self.ip
        assert 'dummyX' not in self.ip

        self.ip.bala.ifname = 'dummyX'
        self.ip.bala.commit()

        self.ip._links_event.wait()
        assert 'bala' not in self.ip
        assert 'dummyX' in self.ip

    def test_updown(self):
        require_user('root')
        assert not (self.ip.dummyX.flags & 1)

        self.ip.dummyX.up()
        self.ip.dummyX.commit()
        assert self.ip.dummyX.flags & 1

        self.ip.dummyX.down()
        self.ip.dummyX.commit()
        assert not (self.ip.dummyX.flags & 1)

    def test_create_fail(self):
        require_user('root')
        assert 'bala' not in self.ip
        # create with mac 11:22:33:44:55:66 should fail
        i = self.ip.create(kind='dummy',
                           ifname='bala',
                           address='11:22:33:44:55:66')
        try:
            i.commit()
        except NetlinkSocketError:
            pass

        assert i._mode == 'invalid'
        assert 'bala' not in self.ip

    def test_create_plain(self):
        require_user('root')
        assert 'bala' not in self.ip
        i = self.ip.create(kind='dummy', ifname='bala')
        i.add_ip('172.16.14.1/24')
        i.commit()
        assert '172.16.14.1/24' in get_ip_addr(interface='bala')
        remove_link('bala')

    def test_create_context(self):
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
        assert self.ip.bala_port0.if_master == self.ip.bala.index
        assert self.ip.bala_port1.if_master == self.ip.bala.index

        with self.ip.bala as i:
            i.del_port(self.ip.bala_port0)
            i.del_port(self.ip.bala_port1)
            i.del_ip('172.16.15.1/24')

        self.ip._links_event.wait()
        assert '172.16.15.1/24' not in get_ip_addr(interface='bala')
        #assert self.ip.bala_port0.if_master is None
        #assert self.ip.bala_port1.if_master is None

        remove_link('bala_port0')
        remove_link('bala_port1')
        remove_link('bala')

    def test_create_vlan(self):
        require_user('root')
        assert 'bala' not in self.ip
        assert 'bv101' not in self.ip

        self.ip.create(kind='dummy',
                       ifname='bala').commit()
        self.ip.create(kind='vlan',
                       ifname='bv101',
                       link=self.ip.bala.index,
                       vlan_id=101).commit()

        assert self.ip.bv101.if_master == self.ip.bala.index
        remove_link('bv101')
        remove_link('bala')
