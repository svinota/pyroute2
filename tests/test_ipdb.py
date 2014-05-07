import time
from pyroute2 import IPDB
from pyroute2.common import basestring
from pyroute2.netlink import NetlinkError
from pyroute2.netlink.ipdb import clear_fail_bit
from pyroute2.netlink.ipdb import set_fail_bit
from pyroute2.netlink.ipdb import _FAIL_COMMIT
from pyroute2.netlink.ipdb import _FAIL_ROLLBACK
from utils import grep
from utils import create_link
from utils import remove_link
from utils import require_user
from utils import require_8021q
from utils import require_bond
from utils import require_bridge
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
        for name in ('bala_port0', 'bala_port1', 'dummyX',
                     'bala', 'bv101'):
            try:
                with self.ip.interfaces[name] as i:
                    i.remove()
            except KeyError:
                pass
            except NetlinkError as e:
                if e.code != 19:  # No such device
                    raise
        self.ip.release()

    def test_simple(self):
        assert len(list(self.ip.interfaces.keys())) > 0

    def test_empty_transaction(self):
        assert 'lo' in self.ip.interfaces
        with self.ip.interfaces.lo as i:
            assert isinstance(i.mtu, int)

    def test_idx_len(self):
        assert len(self.ip.by_name.keys()) == len(self.ip.by_index.keys())

    def test_idx_set(self):
        assert set(self.ip.by_name.values()) == set(self.ip.by_index.values())

    def test_idx_types(self):
        assert all(isinstance(i, int) for i in self.ip.by_index.keys())
        assert all(isinstance(i, basestring) for i in self.ip.by_name.keys())

    def test_ips(self):
        for name in self.ip.by_name:
            assert len(self.ip.interfaces[name]['ipaddr']) == \
                len(get_ip_addr(name))

    def test_reprs(self):
        assert isinstance(repr(self.ip.interfaces.lo.ipaddr), basestring)
        assert isinstance(repr(self.ip.interfaces.lo), basestring)

    def test_dotkeys(self):
        # self.ip.lo hint for ipython
        assert 'lo' in dir(self.ip.interfaces)
        assert 'lo' in self.ip.interfaces
        assert self.ip.interfaces.lo == self.ip.interfaces['lo']
        # create attribute
        self.ip.interfaces['newitem'] = True
        self.ip.interfaces.newattr = True
        self.ip.interfaces.newitem = None
        assert self.ip.interfaces.newitem == self.ip.interfaces['newitem']
        assert self.ip.interfaces.newitem is None
        # delete attribute
        del self.ip.interfaces.newitem
        del self.ip.interfaces.newattr
        assert 'newattr' not in dir(self.ip.interfaces)

    def test_callback_positive(self):
        require_user('root')
        assert 'dummyX' in self.ip.interfaces

        # test callback, that adds an address by itself --
        # just to check the possibility
        def cb(snapshot, transaction):
            self.ip.nl.addr('add',
                            self.ip.interfaces.dummyX.index,
                            address='172.16.22.1',
                            mask=24)

        # register callback and check CB chain length
        self.ip.interfaces.dummyX.register_callback(cb)
        assert len(self.ip.interfaces.dummyX._callbacks) == 1

        # create a transaction and commit it
        if self.ip.interfaces.dummyX._mode == 'explicit':
            self.ip.interfaces.dummyX.begin()
        self.ip.interfaces.dummyX.add_ip('172.16.21.1/24')
        self.ip.interfaces.dummyX.commit()

        # added address should be there
        assert ('172.16.21.1', 24) in self.ip.interfaces.dummyX.ipaddr
        # and the one, added by the callback, too
        assert ('172.16.22.1', 24) in self.ip.interfaces.dummyX.ipaddr

        # unregister callback
        self.ip.interfaces.dummyX.unregister_callback(cb)
        assert len(self.ip.interfaces.dummyX._callbacks) == 0

    def test_callback_negative(self):
        require_user('root')
        assert 'dummyX' in self.ip.interfaces

        # test exception to differentiate
        class CBException(Exception):
            pass

        # test callback, that always fail
        def cb(snapshot, transaction):
            raise CBException()

        # register callback and check CB chain length
        self.ip.interfaces.dummyX.register_callback(cb)
        assert len(self.ip.interfaces.dummyX._callbacks) == 1

        # create a transaction and commit it; should fail
        # 'cause of the callback
        if self.ip.interfaces.dummyX._mode == 'explicit':
            self.ip.interfaces.dummyX.begin()
        self.ip.interfaces.dummyX.add_ip('172.16.21.1/24')
        try:
            self.ip.interfaces.dummyX.commit()
        except CBException:
            pass

        # added address should be removed
        assert ('172.16.21.1', 24) not in self.ip.interfaces.dummyX.ipaddr

        # unregister callback
        self.ip.interfaces.dummyX.unregister_callback(cb)
        assert len(self.ip.interfaces.dummyX._callbacks) == 0

    def test_review(self):
        assert len(self.ip.interfaces.lo._tids) == 0
        if self.ip.interfaces.lo._mode == 'explicit':
            self.ip.interfaces.lo.begin()
        self.ip.interfaces.lo.add_ip('172.16.21.1/24')
        r = self.ip.interfaces.lo.review()
        assert len(r['+ipaddr']) == 1
        assert len(r['-ipaddr']) == 0
        assert len(r['+ports']) == 0
        assert len(r['-ports']) == 0
        # +/-ipaddr, +/-ports
        assert len([i for i in r if r[i] is not None]) == 4
        self.ip.interfaces.lo.drop()

    def test_rename(self):
        require_user('root')
        assert 'bala' not in self.ip.interfaces
        assert 'dummyX' in self.ip.interfaces

        if self.ip.interfaces.dummyX._mode == 'explicit':
            self.ip.interfaces.dummyX.begin()
        self.ip.interfaces.dummyX.ifname = 'bala'
        self.ip.interfaces.dummyX.commit()

        assert 'bala' in self.ip.interfaces
        assert 'dummyX' not in self.ip.interfaces

        if self.ip.interfaces.bala._mode == 'explicit':
            self.ip.interfaces.bala.begin()
        self.ip.interfaces.bala.ifname = 'dummyX'
        self.ip.interfaces.bala.commit()

        assert 'bala' not in self.ip.interfaces
        assert 'dummyX' in self.ip.interfaces

    def test_routes(self):
        require_user('root')
        assert '172.16.0.0/24' not in self.ip.routes

        # create a route
        with self.ip.routes.add({'dst': '172.16.0.0/24',
                                 'gateway': '127.0.0.1'}) as r:
            pass
        assert '172.16.0.0/24' in self.ip.routes
        assert grep('ip ro', pattern='172.16.0.0/24.*127.0.0.1')

        # change a route
        with self.ip.routes['172.16.0.0/24'] as r:
            r.gateway = '127.0.0.2'
        assert self.ip.routes['172.16.0.0/24'].gateway == '127.0.0.2'
        assert grep('ip ro', pattern='172.16.0.0/24.*127.0.0.2')

        # delete a route
        with self.ip.routes['172.16.0.0/24'] as r:
            r.remove()
        assert '172.16.0.0/24' not in self.ip.routes
        assert not grep('ip ro', pattern='172.16.0.0/24')

    def _test_shadow(self, kind):
        a = self.ip.create(ifname='bala', kind=kind).commit()
        if a._mode == 'explicit':
            a.begin()
        a.shadow().commit()
        assert 'bala' in self.ip.interfaces
        assert not grep('ip link', pattern='bala')
        b = self.ip.create(ifname='bala', kind=kind).commit()
        assert a == b
        assert grep('ip link', pattern='bala')

    def test_shadow_bond(self):
        require_user('root')
        require_bond()
        self._test_shadow('bond')

    def test_shadow_bridge(self):
        require_user('root')
        require_bridge()
        self._test_shadow('bridge')

    def test_shadow_dummy(self):
        require_user('root')
        self._test_shadow('dummy')

    def test_updown(self):
        require_user('root')
        assert not (self.ip.interfaces.dummyX.flags & 1)

        if self.ip.interfaces.dummyX._mode == 'explicit':
            self.ip.interfaces.dummyX.begin()
        self.ip.interfaces.dummyX.up()
        self.ip.interfaces.dummyX.commit()
        assert self.ip.interfaces.dummyX.flags & 1

        if self.ip.interfaces.dummyX._mode == 'explicit':
            self.ip.interfaces.dummyX.begin()
        self.ip.interfaces.dummyX.down()
        self.ip.interfaces.dummyX.commit()
        assert not (self.ip.interfaces.dummyX.flags & 1)

    def test_cfail_rollback(self):
        require_user('root')
        require_bridge()

        # create ports
        with self.ip.create(kind='dummy', ifname='bala_port0'):
            pass
        with self.ip.create(kind='dummy', ifname='bala_port1'):
            pass
        assert 'bala_port0' in self.ip.interfaces
        assert 'bala_port1' in self.ip.interfaces

        # commits should fail
        clear_fail_bit(_FAIL_COMMIT)
        clear_fail_bit(_FAIL_ROLLBACK)
        try:
            # create bridge
            with self.ip.create(kind='bridge', ifname='bala') as i:
                i.add_ip('172.16.0.1/24')
                i.add_ip('172.16.0.2/24')
                i.add_port(self.ip.interfaces.bala_port0)
                i.add_port(self.ip.interfaces.bala_port1)

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
        assert 'bala' in self.ip.interfaces
        assert 'bala_port0' in self.ip.interfaces
        assert 'bala_port1' in self.ip.interfaces
        assert ('172.16.0.1', 24) not in self.ip.interfaces.bala.ipaddr
        assert ('172.16.0.2', 24) not in self.ip.interfaces.bala.ipaddr
        assert self.ip.interfaces.bala_port0.index not in \
            self.ip.interfaces.bala.ports
        assert self.ip.interfaces.bala_port1.index not in \
            self.ip.interfaces.bala.ports

    def test_cfail_commit(self):
        require_user('root')
        require_bridge()

        # create ports
        with self.ip.create(kind='dummy', ifname='bala_port0'):
            pass
        with self.ip.create(kind='dummy', ifname='bala_port1'):
            pass
        assert 'bala_port0' in self.ip.interfaces
        assert 'bala_port1' in self.ip.interfaces

        # commits should fail
        clear_fail_bit(_FAIL_COMMIT)
        try:
            # create bridge
            with self.ip.create(kind='bridge', ifname='bala') as i:
                i.add_ip('172.16.0.1/24')
                i.add_ip('172.16.0.2/24')
                i.add_port(self.ip.interfaces.bala_port0)
                i.add_port(self.ip.interfaces.bala_port1)

        except AssertionError:
            pass

        finally:
            # set bit again
            set_fail_bit(_FAIL_COMMIT)

        # expected results:
        # 1. interface created
        # 2. no addresses
        # 3. no ports
        assert 'bala' in self.ip.interfaces
        assert 'bala_port0' in self.ip.interfaces
        assert 'bala_port1' in self.ip.interfaces
        assert ('172.16.0.1', 24) not in self.ip.interfaces.bala.ipaddr
        assert ('172.16.0.2', 24) not in self.ip.interfaces.bala.ipaddr
        assert self.ip.interfaces.bala_port0.index not in \
            self.ip.interfaces.bala.ports
        assert self.ip.interfaces.bala_port1.index not in \
            self.ip.interfaces.bala.ports

    def test_create_fail(self):
        require_user('root')
        assert 'bala' not in self.ip.interfaces
        # create with mac 11:22:33:44:55:66 should fail
        i = self.ip.create(kind='dummy',
                           ifname='bala',
                           address='11:22:33:44:55:66')
        try:
            i.commit()
        except NetlinkError:
            pass

        assert i._mode == 'invalid'
        assert 'bala' not in self.ip.interfaces

    def test_create_plain(self):
        require_user('root')
        assert 'bala' not in self.ip.interfaces
        i = self.ip.create(kind='dummy', ifname='bala')
        i.add_ip('172.16.0.1/24')
        i.commit()
        assert ('172.16.0.1', 24) in self.ip.interfaces.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')

    def test_create_and_remove(self):
        require_user('root')
        assert 'bala' not in self.ip.interfaces

        with self.ip.create(kind='dummy', ifname='bala') as i:
            i.add_ip('172.16.0.1/24')
        assert ('172.16.0.1', 24) in self.ip.interfaces.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')

        with self.ip.interfaces.bala as i:
            i.remove()
        assert 'bala' not in self.ip.interfaces

    def _create_master(self, kind):
        require_user('root')
        assert 'bala' not in self.ip.interfaces
        assert 'bala_port0' not in self.ip.interfaces
        assert 'bala_port1' not in self.ip.interfaces

        self.ip.create(kind='dummy', ifname='bala_port0').commit()
        self.ip.create(kind='dummy', ifname='bala_port1').commit()

        with self.ip.create(kind=kind, ifname='bala') as i:
            i.add_port(self.ip.interfaces.bala_port0)
            i.add_port(self.ip.interfaces.bala_port1)
            i.add_ip('172.16.0.1/24')

        assert ('172.16.0.1', 24) in self.ip.interfaces.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')
        assert self.ip.interfaces.bala_port0.if_master == \
            self.ip.interfaces.bala.index
        assert self.ip.interfaces.bala_port1.if_master == \
            self.ip.interfaces.bala.index

        with self.ip.interfaces.bala as i:
            i.del_port(self.ip.interfaces.bala_port0)
            i.del_port(self.ip.interfaces.bala_port1)
            i.del_ip('172.16.0.1/24')

        assert ('172.16.0.1', 24) not in self.ip.interfaces.bala.ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface='bala')
        assert self.ip.interfaces.bala_port0.if_master is None
        assert self.ip.interfaces.bala_port1.if_master is None

    def test_create_bridge(self):
        require_bridge()
        self._create_master('bridge')

    def test_create_bond(self):
        require_bond()
        self._create_master('bond')

    def test_create_vlan_by_interface(self):
        require_user('root')
        require_8021q()
        assert 'bala' not in self.ip.interfaces
        assert 'bv101' not in self.ip.interfaces

        self.ip.create(kind='dummy',
                       ifname='bala').commit()
        self.ip.create(kind='vlan',
                       ifname='bv101',
                       link=self.ip.interfaces.bala,
                       vlan_id=101).commit()

        assert self.ip.interfaces.bv101.if_master == \
            self.ip.interfaces.bala.index

    def test_create_vlan_by_index(self):
        require_user('root')
        require_8021q()
        assert 'bala' not in self.ip.interfaces
        assert 'bv101' not in self.ip.interfaces

        self.ip.create(kind='dummy',
                       ifname='bala').commit()
        self.ip.create(kind='vlan',
                       ifname='bv101',
                       link=self.ip.interfaces.bala.index,
                       vlan_id=101).commit()

        assert self.ip.interfaces.bv101.if_master == \
            self.ip.interfaces.bala.index

    def test_remove_secondaries(self):
        require_user('root')
        assert 'bala' not in self.ip.interfaces

        with self.ip.create(kind='dummy', ifname='bala') as i:
            i.add_ip('172.16.0.1', 24)
            i.add_ip('172.16.0.2', 24)

        assert 'bala' in self.ip.interfaces
        assert ('172.16.0.1', 24) in self.ip.interfaces.bala.ipaddr
        assert ('172.16.0.2', 24) in self.ip.interfaces.bala.ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface='bala')
        assert '172.16.0.2/24' in get_ip_addr(interface='bala')

        if i._mode == 'explicit':
            i.begin()

        i.del_ip('172.16.0.1', 24)
        i.del_ip('172.16.0.2', 24)
        i.commit()

        assert ('172.16.0.1', 24) not in self.ip.interfaces.bala.ipaddr
        assert ('172.16.0.2', 24) not in self.ip.interfaces.bala.ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface='bala')
        assert '172.16.0.2/24' not in get_ip_addr(interface='bala')


class TestFork(TestExplicit):

    def setup(self):
        create_link('dummyX', 'dummy')
        self.ip = IPDB(mode=self.mode, fork=True)


class TestImplicit(TestExplicit):
    mode = 'implicit'

    def test_chain(self):
        require_user('root')
        i = self.ip.create(ifname='bala', kind='dummy')
        i.commit().up().commit()
        assert self.ip.interfaces.bala.flags & 1

        i.add_ip('172.16.0.1/24').down().commit()
        assert ('172.16.0.1', 24) in self.ip.interfaces.bala.ipaddr
        assert not (self.ip.interfaces.bala.flags & 1)

        i.remove().commit()
        assert 'bala' not in self.ip.interfaces

    def test_generic_pre_callback(self):
        require_user('root')

        def cb(ipdb, msg, action):
            if action == 'RTM_NEWLINK':
                # fake the incoming message
                msg['flags'] = 1234

        # register callback
        self.ip.register_callback(cb, mode='pre')
        # create an interface bala
        self.ip.create(kind='dummy', ifname='bala').commit()
        # assert flags
        assert self.ip.interfaces.bala.flags == 1234
        # cleanup
        self.ip.unregister_callback(cb, mode='pre')
        self.ip.interfaces.bala.remove()
        self.ip.interfaces.bala.commit()

    def test_generic_post_callback(self):
        require_user('root')
        require_bridge()

        def cb(ipdb, msg, action):
            if action == 'RTM_NEWLINK' and \
                    msg.get_attr('IFLA_IFNAME', '').startswith('bala_port'):
                with ipdb.exclusive:
                    obj = ipdb.interfaces[msg['index']]
                    ipdb.interfaces.bala.add_port(obj)
                    ipdb.interfaces.bala.commit()

        # create bridge
        self.ip.create(kind='bridge', ifname='bala').commit()
        # wait the bridge to be created
        self.ip.wait_interface(ifname='bala')
        # register callback
        self.ip.register_callback(cb)
        # create ports
        self.ip.create(kind='dummy', ifname='bala_port0').commit()
        self.ip.create(kind='dummy', ifname='bala_port1').commit()
        # sleep for interfaces
        self.ip.wait_interface(ifname='bala_port0')
        self.ip.wait_interface(ifname='bala_port1')
        time.sleep(1)
        # check that ports are attached
        assert self.ip.interfaces.bala_port0.index in \
            self.ip.interfaces.bala.ports
        assert self.ip.interfaces.bala_port1.index in \
            self.ip.interfaces.bala.ports
        # unregister callback
        self.ip.unregister_callback(cb)


class TestDirect(object):

    def setup(self):
        create_link('dummyX', 'dummy')
        self.ip = IPDB(mode='direct')

    def teardown(self):
        self.ip.release()
        remove_link('dummyX')

    def test_context_fail(self):
        try:
            with self.ip.interfaces.lo as i:
                i.down()
        except TypeError:
            pass

    def test_updown(self):
        require_user('root')

        assert not (self.ip.interfaces.dummyX.flags & 1)
        self.ip.interfaces.dummyX.up()

        assert self.ip.interfaces.dummyX.flags & 1
        self.ip.interfaces.dummyX.down()

        assert not (self.ip.interfaces.dummyX.flags & 1)

    def test_exceptions_last(self):
        try:
            self.ip.interfaces.lo.last()
        except TypeError:
            pass

    def test_exception_review(self):
        try:
            self.ip.interfaces.lo.review()
        except TypeError:
            pass


class TestMisc(object):

    def setup(self):
        create_link('dummyX', 'dummy')

    def teardown(self):
        remove_link('dummyX')

    def test_fail_released(self):
        ip = IPDB()
        ip.release()
        try:
            ip.interfaces.lo.up()
        except RuntimeError:
            pass

    def test_context_manager(self):
        with IPDB() as ip:
            assert ip.interfaces.lo.index == 1

    def _test_break_netlink(self):
        ip = IPDB()
        s = tuple(ip.nl._sockets)[0]
        s.close()
        ip.nl._sockets = tuple()
        try:
            ip.interfaces.lo.reload()
        except IOError:
            pass
        del s
        ip.nl.release()

    def test_context_exception_in_code(self):
        try:
            with IPDB(mode='explicit') as ip:
                with ip.interfaces.lo as i:
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
            assert ('172.16.9.1', 24) not in ip.interfaces.lo.ipaddr

    def test_context_exception_in_transaction(self):
        require_user('root')

        with IPDB(mode='explicit') as ip:
            with ip.interfaces.dummyX as i:
                i.add_ip('172.16.0.1/24')

        try:
            with IPDB(mode='explicit') as ip:
                with ip.interfaces.dummyX as i:
                    i.add_ip('172.16.9.1/24')
                    i.del_ip('172.16.0.1/24')
                    i.address = '11:22:33:44:55:66'
        except NetlinkError:
            pass

        with IPDB() as ip:
            assert ('172.16.0.1', 24) in ip.interfaces.dummyX.ipaddr
            assert ('172.16.9.1', 24) not in ip.interfaces.dummyX.ipaddr

    def test_modes(self):
        with IPDB(mode='explicit') as i:
            # transaction required
            try:
                i.interfaces.lo.up()
            except TypeError:
                pass

        with IPDB(mode='implicit') as i:
            # transaction aut-begin()
            assert len(i.interfaces.lo._tids) == 0
            i.interfaces.lo.up()
            assert len(i.interfaces.lo._tids) == 1
            i.interfaces.lo.drop()
            assert len(i.interfaces.lo._tids) == 0

        with IPDB(mode='invalid') as i:
            # transaction mode not supported
            try:
                i.interfaces.lo.up()
            except TypeError:
                pass
