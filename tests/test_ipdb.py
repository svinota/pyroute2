from pyroute2 import IPDB
from pyroute2.netlink import NetlinkError
from pyroute2.netlink.ipdb import clear_fail_bit
from pyroute2.netlink.ipdb import set_fail_bit
from pyroute2.netlink.ipdb import set_ancient
from pyroute2.netlink.ipdb import _FAIL_COMMIT
from pyroute2.netlink.ipdb import _FAIL_ROLLBACK
from utils import create_link
from utils import remove_link
from utils import require_user
from utils import get_ip_addr


class _TestException(Exception):
    pass


class TestExplicit(object):
    ip = None
    mode = 'explicit'

    def setup(self):
        create_link('dummyX', 'dummy')
        self.ip = IPDB(mode=self.mode)

    def teardown(self):
        self.ip.release()
        remove_link('bala_port0')
        remove_link('bala_port1')
        remove_link('dummyX')
        remove_link('bala')
        remove_link('bv101')

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
        assert len(self.ip.lo._tids) == 0
        if self.ip.lo._mode == 'explicit':
            self.ip.lo.begin()
        self.ip.lo.add_ip('172.16.21.1/24')
        r = self.ip.lo.review()
        assert len(r['+ipaddr']) == 1
        assert len(r['-ipaddr']) == 0
        assert len(r['+ports']) == 0
        assert len(r['-ports']) == 0
        # flags, +/-ipaddr, +/-ports
        assert len([i for i in r if r[i] is not None]) == 5
        self.ip.lo.drop()

    def test_rename(self):
        require_user('root')
        assert 'bala' not in self.ip
        assert 'dummyX' in self.ip

        if self.ip.dummyX._mode == 'explicit':
            self.ip.dummyX.begin()
        self.ip.dummyX.ifname = 'bala'
        self.ip.dummyX.commit()

        assert 'bala' in self.ip
        assert 'dummyX' not in self.ip

        if self.ip.bala._mode == 'explicit':
            self.ip.bala.begin()
        self.ip.bala.ifname = 'dummyX'
        self.ip.bala.commit()

        assert 'bala' not in self.ip
        assert 'dummyX' in self.ip

    def test_updown(self):
        require_user('root')
        assert not (self.ip.dummyX.flags & 1)

        if self.ip.dummyX._mode == 'explicit':
            self.ip.dummyX.begin()
        self.ip.dummyX.up()
        self.ip.dummyX.commit()
        assert self.ip.dummyX.flags & 1

        if self.ip.dummyX._mode == 'explicit':
            self.ip.dummyX.begin()
        self.ip.dummyX.down()
        self.ip.dummyX.commit()
        assert not (self.ip.dummyX.flags & 1)

    def test_ancient_bridge(self):
        require_user('root')

        # create ports
        with self.ip.create(kind='dummy', ifname='bala_port0'):
            pass
        with self.ip.create(kind='dummy', ifname='bala_port1'):
            pass
        assert 'bala_port0' in self.ip
        assert 'bala_port1' in self.ip

        set_ancient(True)

        # create bridge
        try:
            with self.ip.create(kind='bridge', ifname='bala') as i:
                i.add_ip('172.16.0.1/24')
                i.add_ip('172.16.0.2/24')
                i.add_port(self.ip.bala_port0)
                i.add_port(self.ip.bala_port1)
        finally:
            set_ancient(False)

        assert 'bala' in self.ip
        assert 'bala_port0' in self.ip
        assert 'bala_port1' in self.ip
        assert ('172.16.0.1', 24) in self.ip.bala.ipaddr
        assert ('172.16.0.2', 24) in self.ip.bala.ipaddr
        assert self.ip.bala_port0.index in self.ip.bala.ports
        assert self.ip.bala_port1.index in self.ip.bala.ports

    def test_cfail_rollback(self):
        require_user('root')

        # create ports
        with self.ip.create(kind='dummy', ifname='bala_port0'):
            pass
        with self.ip.create(kind='dummy', ifname='bala_port1'):
            pass
        assert 'bala_port0' in self.ip
        assert 'bala_port1' in self.ip

        # commits should fail
        clear_fail_bit(_FAIL_COMMIT)
        clear_fail_bit(_FAIL_ROLLBACK)
        try:
            # create bridge
            with self.ip.create(kind='bridge', ifname='bala') as i:
                i.add_ip('172.16.0.1/24')
                i.add_ip('172.16.0.2/24')
                i.add_port(self.ip.bala_port0)
                i.add_port(self.ip.bala_port1)

        except RuntimeError:
            pass

        finally:
            # set bit again
            set_fail_bit(_FAIL_COMMIT)
            set_fail_bit(_FAIL_ROLLBACK)

        # expected results:
        # 1. interface created
        # 2. no addresses
        # 3. no ports
        assert 'bala' in self.ip
        assert 'bala_port0' in self.ip
        assert 'bala_port1' in self.ip
        assert ('172.16.0.1', 24) not in self.ip.bala.ipaddr
        assert ('172.16.0.2', 24) not in self.ip.bala.ipaddr
        assert self.ip.bala_port0.index not in self.ip.bala.ports
        assert self.ip.bala_port1.index not in self.ip.bala.ports

    def test_cfail_commit(self):
        require_user('root')

        # create ports
        with self.ip.create(kind='dummy', ifname='bala_port0'):
            pass
        with self.ip.create(kind='dummy', ifname='bala_port1'):
            pass
        assert 'bala_port0' in self.ip
        assert 'bala_port1' in self.ip

        # commits should fail
        clear_fail_bit(_FAIL_COMMIT)
        try:
            # create bridge
            with self.ip.create(kind='bridge', ifname='bala') as i:
                i.add_ip('172.16.0.1/24')
                i.add_ip('172.16.0.2/24')
                i.add_port(self.ip.bala_port0)
                i.add_port(self.ip.bala_port1)

        except AssertionError:
            pass

        finally:
            # set bit again
            set_fail_bit(_FAIL_COMMIT)

        # expected results:
        # 1. interface created
        # 2. no addresses
        # 3. no ports
        assert 'bala' in self.ip
        assert 'bala_port0' in self.ip
        assert 'bala_port1' in self.ip
        assert ('172.16.0.1', 24) not in self.ip.bala.ipaddr
        assert ('172.16.0.2', 24) not in self.ip.bala.ipaddr
        assert self.ip.bala_port0.index not in self.ip.bala.ports
        assert self.ip.bala_port1.index not in self.ip.bala.ports

    def test_create_fail(self):
        require_user('root')
        assert 'bala' not in self.ip
        # create with mac 11:22:33:44:55:66 should fail
        i = self.ip.create(kind='dummy',
                           ifname='bala',
                           address='11:22:33:44:55:66')
        try:
            i.commit()
        except NetlinkError:
            pass

        assert i._mode == 'invalid'
        assert 'bala' not in self.ip

    def test_create_plain(self):
        require_user('root')
        assert 'bala' not in self.ip
        i = self.ip.create(kind='dummy', ifname='bala')
        i.add_ip('172.16.0.1/24')
        i.commit()
        assert ('172.16.0.1', 24) in self.ip.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')

    def test_create_context(self):
        require_user('root')
        assert 'bala' not in self.ip
        with self.ip.create(kind='dummy', ifname='bala') as i:
            i.add_ip('172.16.0.1/24')
        assert ('172.16.0.1', 24) in self.ip.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')

    def _create_master(self, kind):
        require_user('root')
        assert 'bala' not in self.ip
        assert 'bala_port0' not in self.ip
        assert 'bala_port1' not in self.ip

        self.ip.create(kind='dummy', ifname='bala_port0').commit()
        self.ip.create(kind='dummy', ifname='bala_port1').commit()

        with self.ip.create(kind=kind, ifname='bala') as i:
            i.add_port(self.ip.bala_port0)
            i.add_port(self.ip.bala_port1)
            i.add_ip('172.16.0.1/24')

        assert ('172.16.0.1', 24) in self.ip.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')
        assert self.ip.bala_port0.if_master == self.ip.bala.index
        assert self.ip.bala_port1.if_master == self.ip.bala.index

        with self.ip.bala as i:
            i.del_port(self.ip.bala_port0)
            i.del_port(self.ip.bala_port1)
            i.del_ip('172.16.0.1/24')

        assert ('172.16.0.1', 24) not in self.ip.bala.ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface='bala')
        assert self.ip.bala_port0.if_master is None
        assert self.ip.bala_port1.if_master is None

    def test_create_bridge(self):
        self._create_master('bridge')

    def test_create_bond(self):
        self._create_master('bond')

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

    def test_remove_secondaries(self):
        require_user('root')
        assert 'bala' not in self.ip

        with self.ip.create(kind='dummy', ifname='bala') as i:
            i.add_ip('172.16.0.1', 24)
            i.add_ip('172.16.0.2', 24)

        assert 'bala' in self.ip
        assert ('172.16.0.1', 24) in self.ip.bala.ipaddr
        assert ('172.16.0.2', 24) in self.ip.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')
        assert '172.16.0.2/24' in get_ip_addr(interface='bala')

        if i._mode == 'explicit':
            i.begin()

        i.del_ip('172.16.0.1', 24)
        i.del_ip('172.16.0.2', 24)
        i.commit()

        assert ('172.16.0.1', 24) not in self.ip.bala.ipaddr
        assert ('172.16.0.2', 24) not in self.ip.bala.ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface='bala')
        assert '172.16.0.2/24' not in get_ip_addr(interface='bala')


class TestImplicit(TestExplicit):
    mode = 'implicit'


class TestDirect(object):

    def setup(self):
        create_link('dummyX', 'dummy')
        self.ip = IPDB(mode='direct')

    def teardown(self):
        self.ip.release()
        remove_link('dummyX')

    def test_context_fail(self):
        try:
            with self.ip.lo as i:
                i.down()
        except TypeError:
            pass

    def test_updown(self):
        require_user('root')

        assert not (self.ip.dummyX.flags & 1)
        self.ip.dummyX.up()

        assert self.ip.dummyX.flags & 1
        self.ip.dummyX.down()

        assert not (self.ip.dummyX.flags & 1)

    def test_exceptions_last(self):
        try:
            self.ip.lo.last()
        except TypeError:
            pass

    def test_exception_review(self):
        try:
            self.ip.lo.review()
        except TypeError:
            pass


class TestMisc(object):

    def setup(self):
        create_link('dummyX', 'dummy')

    def teardown(self):
        remove_link('dummyX')

    def test_context_manager(self):
        with IPDB() as ip:
            assert ip.lo.index == 1

    def test_break_netlink(self):
        ip = IPDB()
        s = tuple(ip.ip._sockets)[0]
        s.close()
        ip.ip._sockets = tuple()
        try:
            ip.lo.reload()
        except IOError:
            pass
        del s
        ip.ip.release()

    def test_context_exception_in_code(self):
        try:
            with IPDB(mode='explicit') as ip:
                with ip.lo as i:
                    i.add_ip('172.16.9.1/24')
                    # normally, this code is never reached
                    # but we should test it anyway
                    del i['flags']
                    # hands up!
                    raise _TestException()
        except _TestException:
            pass

        # check that the netlink socket is properly closed
        # and transaction was really dropped
        with IPDB() as ip:
            assert ('172.16.9.1', 24) not in ip.lo.ipaddr

    def test_context_exception_in_transaction(self):
        require_user('root')

        with IPDB(mode='explicit') as ip:
            with ip.dummyX as i:
                i.add_ip('172.16.0.1/24')

        try:
            with IPDB(mode='explicit') as ip:
                with ip.dummyX as i:
                    i.add_ip('172.16.9.1/24')
                    i.del_ip('172.16.0.1/24')
                    i.address = '11:22:33:44:55:66'
        except NetlinkError:
            pass

        with IPDB() as ip:
            assert ('172.16.0.1', 24) in ip.dummyX.ipaddr
            assert ('172.16.9.1', 24) not in ip.dummyX.ipaddr

    def test_modes(self):
        with IPDB(mode='explicit') as i:
            # transaction required
            try:
                i.lo.up()
            except TypeError:
                pass

        with IPDB(mode='implicit') as i:
            # transaction aut-begin()
            assert len(i.lo._tids) == 0
            i.lo.up()
            assert len(i.lo._tids) == 1
            i.lo.drop()
            assert len(i.lo._tids) == 0

        with IPDB(mode='invalid') as i:
            # transaction mode not supported
            try:
                i.lo.up()
            except TypeError:
                pass
