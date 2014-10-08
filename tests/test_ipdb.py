# -*- coding: utf-8 -*-

import json
import socket
from pyroute2 import IPDB
from pyroute2 import IPRoute
from pyroute2.common import basestring
from pyroute2.common import AddrPool
from pyroute2.netlink import NetlinkError
from pyroute2.ipdb import CreateException
from pyroute2.ipdb import clear_fail_bit
from pyroute2.ipdb import set_fail_bit
from pyroute2.ipdb import _FAIL_COMMIT
from pyroute2.ipdb import _FAIL_ROLLBACK
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
        self.ap = AddrPool()
        self.iftmp = 'pr2x{0}'
        self.ifaces = []
        self.ifd = self.get_ifname()
        create_link(self.ifd, kind='dummy')
        self.ip = IPDB(mode=self.mode)

    def get_ifname(self):
        naddr = self.ap.alloc()
        ifname = self.iftmp.format(naddr)
        self.ifaces.append(ifname)
        return ifname

    def teardown(self):
        self.ip.release()
        for name in self.ifaces:
            remove_link(name)
        self.ifaces = []

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

    def test_vlan_slave_bridge(self):
        # https://github.com/svinota/pyroute2/issues/58
        # based on the code by Petr Horáček
        dXname = self.get_ifname()
        vXname = self.get_ifname()
        vYname = self.get_ifname()
        brname = self.get_ifname()

        require_user('root')
        dX = self.ip.create(ifname=dXname, kind='dummy').commit()
        vX = self.ip.create(ifname=vXname, kind='vlan',
                            link=dX, vlan_id=101).commit()
        vY = self.ip.create(ifname=vYname, kind='vlan',
                            link=dX, vlan_id=102).commit()
        with self.ip.create(ifname=brname, kind='bridge') as i:
            i.add_port(vX)
            i.add_port(vY['index'])

        assert vX['index'] in self.ip.interfaces[brname]['ports']
        assert vY['index'] in self.ip.interfaces[brname].ports
        assert vX['link'] == dX['index']
        assert vY['link'] == dX['index']
        assert vX['master'] == self.ip.interfaces[brname]['index']
        assert vY['master'] == self.ip.interfaces[brname].index

    def _test_commit_hook_positive(self):
        require_user('root')

        # test callback, that adds an address by itself --
        # just to check the possibility
        def cb(interface, snapshot, transaction):
            self.ip.nl.addr('add',
                            self.ip.interfaces[self.ifd].index,
                            address='172.16.22.1',
                            mask=24)

        # register callback and check CB chain length
        self.ip.interfaces[self.ifd].register_commit_hook(cb)
        assert len(self.ip.interfaces[self.ifd]._commit_hooks) == 1

        # create a transaction and commit it
        if self.ip.interfaces[self.ifd]._mode == 'explicit':
            self.ip.interfaces[self.ifd].begin()
        self.ip.interfaces[self.ifd].add_ip('172.16.21.1/24')
        self.ip.interfaces[self.ifd].commit()

        # added address should be there
        assert ('172.16.21.1', 24) in \
            self.ip.interfaces[self.ifd].ipaddr
        # and the one, added by the callback, too
        assert ('172.16.22.1', 24) in \
            self.ip.interfaces[self.ifd].ipaddr

        # unregister callback
        self.ip.interfaces[self.ifd].unregister_commit_hook(cb)
        assert len(self.ip.interfaces[self.ifd]._commit_hooks) == 0

    def _test_commit_hook_negative(self):
        require_user('root')

        # test exception to differentiate
        class CBException(Exception):
            pass

        # test callback, that always fail
        def cb(interface, snapshot, transaction):
            raise CBException()

        # register callback and check CB chain length
        self.ip.interfaces[self.ifd].register_commit_hook(cb)
        assert len(self.ip.interfaces[self.ifd]._commit_hooks) == 1

        # create a transaction and commit it; should fail
        # 'cause of the callback
        if self.ip.interfaces[self.ifd]._mode == 'explicit':
            self.ip.interfaces[self.ifd].begin()
        self.ip.interfaces[self.ifd].add_ip('172.16.21.1/24')
        try:
            self.ip.interfaces[self.ifd].commit()
        except CBException:
            pass

        # added address should be removed
        assert ('172.16.21.1', 24) not in \
            self.ip.interfaces[self.ifd].ipaddr

        # unregister callback
        self.ip.interfaces[self.ifd].unregister_commit_hook(cb)
        assert len(self.ip.interfaces[self.ifd]._commit_hooks) == 0

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

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        self.ip.create(ifname=ifA, kind='dummy').commit()

        if self.ip.interfaces[ifA]._mode == 'explicit':
            self.ip.interfaces[ifA].begin()
        self.ip.interfaces[ifA].ifname = ifB
        self.ip.interfaces[ifA].commit()

        assert ifB in self.ip.interfaces
        assert ifA not in self.ip.interfaces

        if self.ip.interfaces[ifB]._mode == 'explicit':
            self.ip.interfaces[ifB].begin()
        self.ip.interfaces[ifB].ifname = ifA
        self.ip.interfaces[ifB].commit()

        assert ifB not in self.ip.interfaces
        assert ifA in self.ip.interfaces

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
        ifA = self.get_ifname()

        a = self.ip.create(ifname=ifA, kind=kind).commit()
        if a._mode == 'explicit':
            a.begin()
        a.shadow().commit()
        assert ifA in self.ip.interfaces
        assert not grep('ip link', pattern=ifA)
        b = self.ip.create(ifname=ifA, kind=kind).commit()
        assert a == b
        assert grep('ip link', pattern=ifA)

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

        if self.ip.interfaces[self.ifd]._mode == 'explicit':
            self.ip.interfaces[self.ifd].begin()
        self.ip.interfaces[self.ifd].up()
        self.ip.interfaces[self.ifd].commit()
        assert self.ip.interfaces[self.ifd].flags & 1

        if self.ip.interfaces[self.ifd]._mode == 'explicit':
            self.ip.interfaces[self.ifd].begin()
        self.ip.interfaces[self.ifd].down()
        self.ip.interfaces[self.ifd].commit()
        assert not (self.ip.interfaces[self.ifd].flags & 1)

    def _test_cfail_rollback(self):
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

    def _test_cfail_commit(self):
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

    def test_fail_ipaddr(self):
        require_user('root')

        ifA = self.get_ifname()

        i = self.ip.create(ifname=ifA, kind='dummy').commit()
        assert not len(i.ipaddr)
        if i._mode == 'explicit':
            i.begin()
        i.add_ip('123.456.789.1024/153')
        try:
            i.commit()
        except socket.error as e:
            if not e.args[0].startswith('illegal IP'):
                raise
        assert not len(i.ipaddr)
        if i._mode == 'explicit':
            i.begin()
        i.remove().commit()
        assert ifA not in self.ip.interfaces

    def test_json_dump(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        # set up the interface
        with self.ip.create(kind='dummy', ifname=ifA) as i:
            i.add_ip('172.16.0.1/24')
            i.add_ip('172.16.0.2/24')
            i.up()

        # make a backup
        backup = self.ip.interfaces[ifA].dump()
        assert isinstance(backup, dict)

        # remove index -- make it portable
        del backup['index']
        # serialize
        backup = json.dumps(backup)

        # remove the interface
        with self.ip.interfaces[ifA] as i:
            i.remove()

        # create again, but with different name
        self.ip.create(kind='dummy', ifname=ifB).commit()

        # load the backup
        # 1. prepare to the restore: bring it down
        with self.ip.interfaces[ifB] as i:
            i.down()
        # 2. please notice, the interface will be renamed after the backup
        t = self.ip.interfaces[ifB].load(json.loads(backup))
        self.ip.interfaces[ifB].commit(transaction=t)

        # check :)
        assert ifA in self.ip.interfaces
        assert ifB not in self.ip.interfaces
        assert ('172.16.0.1', 24) in self.ip.interfaces[ifA].ipaddr
        assert ('172.16.0.2', 24) in self.ip.interfaces[ifA].ipaddr
        assert self.ip.interfaces[ifA].flags & 1

    def test_freeze(self):
        require_user('root')

        interface = self.ip.interfaces[self.ifd]

        # set up the interface
        with interface as i:
            i.add_ip('172.16.0.1/24')
            i.add_ip('172.16.1.1/24')
            i.up()

        # check
        assert ('172.16.0.1', 24) in interface.ipaddr
        assert ('172.16.1.1', 24) in interface.ipaddr
        assert interface.flags & 1

        # assert routine
        def probe():
            # The freeze results are dynamic: it is not a real freeze,
            # it is a restore routine. So it takes time for results
            # to stabilize
            err = None
            for _ in range(3):
                err = None
                interface.ipaddr.set_target((('172.16.0.1', 24),
                                             ('172.16.1.1', 24)))
                interface.ipaddr.target.wait()
                try:
                    assert ('172.16.0.1', 24) in interface.ipaddr
                    assert ('172.16.1.1', 24) in interface.ipaddr
                    assert interface.flags & 1
                    break
                except AssertionError as e:
                    err = e
                    continue
                except Exception as e:
                    err = e
                    break
            if err is not None:
                interface.unfreeze()
                i2.release()
                raise err

        # freeze
        interface.freeze()

        # change the interface somehow
        i2 = IPRoute()
        i2.addr('delete', interface.index, '172.16.0.1', 24)
        i2.addr('delete', interface.index, '172.16.1.1', 24)
        probe()

        # unfreeze
        self.ip.interfaces[self.ifd].unfreeze()

        try:
            i2.addr('delete', interface.index, '172.16.0.1', 24)
            i2.addr('delete', interface.index, '172.16.1.1', 24)
        except:
            pass
        finally:
            i2.release()

        # should be up, but w/o addresses
        interface.ipaddr.set_target(set())
        interface.ipaddr.target.wait(3)
        assert ('172.16.0.1', 24) not in self.ip.interfaces[self.ifd].ipaddr
        assert ('172.16.1.1', 24) not in self.ip.interfaces[self.ifd].ipaddr
        assert self.ip.interfaces[self.ifd].flags & 1

    def test_snapshots(self):
        require_user('root')

        ifB = self.get_ifname()

        # set up the interface
        with self.ip.interfaces[self.ifd] as i:
            i.add_ip('172.16.0.1/24')
            i.up()

        # check it
        assert ('172.16.0.1', 24) in self.ip.interfaces[self.ifd].ipaddr
        assert self.ip.interfaces[self.ifd].flags & 1

        # make a snapshot
        s = self.ip.interfaces[self.ifd].snapshot()
        i = self.ip.interfaces[self.ifd]

        # check it
        assert i.last_snapshot_id() == s

        # unset the interface
        with self.ip.interfaces[self.ifd] as i:
            i.del_ip('172.16.0.1/24')
            i.down()

        # we can not rename the interface while it is up,
        # so do it in two turns
        with self.ip.interfaces[self.ifd] as i:
            i.ifname = ifB

        # check it
        assert ifB in self.ip.interfaces
        assert self.ifd not in self.ip.interfaces
        y = self.ip.interfaces[ifB]
        assert i == y
        assert ('172.16.0.1', 24) not in y.ipaddr
        assert not (y.flags & 1)

        # revert snapshot
        y.revert(s).commit()

        # check it
        assert ifB not in self.ip.interfaces
        assert self.ifd in self.ip.interfaces
        assert ('172.16.0.1', 24) in self.ip.interfaces[self.ifd].ipaddr
        assert self.ip.interfaces[self.ifd].flags & 1

    def _test_ipv(self, ipv, kind):
        require_user('root')

        ifA = self.get_ifname()

        i = self.ip.create(kind=kind, ifname=ifA).commit()
        if self.ip.interfaces[ifA]._mode == 'explicit':
            self.ip.interfaces[ifA].begin()

        if ipv == 4:
            addr = '172.16.0.1/24'
        elif ipv == 6:
            addr = 'fdb3:84e5:4ff4:55e4::1/64'
        else:
            raise Exception('bad IP version')

        i.add_ip(addr).commit()
        pre_target = addr.split('/')
        target = (pre_target[0], int(pre_target[1]))
        assert target in i['ipaddr']

    def test_ipv4_dummy(self):
        self._test_ipv(4, 'dummy')

    def test_ipv4_bond(self):
        self._test_ipv(4, 'bond')

    def test_ipv4_bridge(self):
        self._test_ipv(4, 'bridge')

    def test_ipv6_dummy(self):
        self._test_ipv(6, 'dummy')

    def test_ipv6_bond(self):
        self._test_ipv(6, 'bond')

    def test_ipv6_bridge(self):
        self._test_ipv(6, 'bridge')

    def test_create_fail(self):
        require_user('root')

        ifA = self.get_ifname()

        # create with mac 11:22:33:44:55:66 should fail
        i = self.ip.create(kind='dummy',
                           ifname=ifA,
                           address='11:22:33:44:55:66')
        try:
            i.commit()
        except NetlinkError:
            pass

        assert i._mode == 'invalid'
        assert ifA not in self.ip.interfaces

    def test_create_dqn(self):
        require_user('root')
        ifA = self.get_ifname()

        i = self.ip.create(kind='dummy', ifname=ifA)
        i.add_ip('172.16.0.1/255.255.255.0')
        i.commit()
        assert ('172.16.0.1', 24) in self.ip.interfaces[ifA].ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface=ifA)

    def test_create_double_reuse(self):
        require_user('root')

        ifA = self.get_ifname()
        # create an interface
        i1 = self.ip.create(kind='dummy', ifname=ifA).commit()
        try:
            # this call should fail on the very first step:
            # `bala` interface already exists
            self.ip.create(kind='dummy', ifname=ifA)
        except CreateException:
            pass
        # add `reuse` keyword -- now should pass
        i2 = self.ip.create(kind='dummy',
                            ifname=ifA,
                            reuse=True).commit()
        # assert that we have got references to the same interface
        assert i1 == i2

    def _create_double(self, kind):
        require_user('root')
        ifA = self.get_ifname()

        self.ip.create(kind=kind, ifname=ifA).commit()
        try:
            self.ip.create(kind=kind, ifname=ifA).commit()
        except CreateException:
            pass

    def test_create_double_dummy(self):
        self._create_double('dummy')

    def test_create_double_bridge(self):
        self._create_double('bridge')

    def test_create_double_bond(self):
        self._create_double('bond')

    def test_create_plain(self):
        require_user('root')
        ifA = self.get_ifname()

        i = self.ip.create(kind='dummy', ifname=ifA)
        i.add_ip('172.16.0.1/24')
        i.commit()
        assert ('172.16.0.1', 24) in self.ip.interfaces[ifA].ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface=ifA)

    def test_create_and_remove(self):
        require_user('root')

        ifA = self.get_ifname()

        with self.ip.create(kind='dummy', ifname=ifA) as i:
            i.add_ip('172.16.0.1/24')
        assert ('172.16.0.1', 24) in self.ip.interfaces[ifA].ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface=ifA)

        with self.ip.interfaces[ifA] as i:
            i.remove()
        assert ifA not in self.ip.interfaces

    def _create_master(self, kind, **kwarg):

        ifM = self.get_ifname()
        ifP1 = self.get_ifname()
        ifP2 = self.get_ifname()

        self.ip.create(kind='dummy', ifname=ifP1).commit()
        self.ip.create(kind='dummy', ifname=ifP2).commit()

        with self.ip.create(kind=kind, ifname=ifM, **kwarg) as i:
            i.add_port(self.ip.interfaces[ifP1])
            i.add_port(self.ip.interfaces[ifP2])
            i.add_ip('172.16.0.1/24')

        assert ('172.16.0.1', 24) in self.ip.interfaces[ifM].ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface=ifM)
        assert self.ip.interfaces[ifP1].if_master == \
            self.ip.interfaces[ifM].index
        assert self.ip.interfaces[ifP2].if_master == \
            self.ip.interfaces[ifM].index

        with self.ip.interfaces[ifM] as i:
            i.del_port(self.ip.interfaces[ifP1])
            i.del_port(self.ip.interfaces[ifP2])
            i.del_ip('172.16.0.1/24')

        assert ('172.16.0.1', 24) not in self.ip.interfaces[ifM].ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface=ifM)
        assert self.ip.interfaces[ifP1].if_master is None
        assert self.ip.interfaces[ifP2].if_master is None

    def test_create_bridge(self):
        require_user('root')
        require_bridge()
        self._create_master('bridge')

    def test_create_bond(self):
        require_user('root')
        require_bond()
        self._create_master('bond')

    def test_create_bond2(self):
        require_user('root')
        require_bond()
        self._create_master('bond', bond_mode=2)

    def test_create_vlan_by_interface(self):
        require_user('root')
        require_8021q()
        ifL = self.get_ifname()
        ifV = self.get_ifname()

        self.ip.create(kind='dummy',
                       ifname=ifL).commit()
        self.ip.create(kind='vlan',
                       ifname=ifV,
                       link=self.ip.interfaces[ifL],
                       vlan_id=101).commit()

        assert self.ip.interfaces[ifV].link == \
            self.ip.interfaces[ifL].index

    def test_create_vlan_by_index(self):
        require_user('root')
        require_8021q()
        ifL = self.get_ifname()
        ifV = self.get_ifname()

        self.ip.create(kind='dummy',
                       ifname=ifL).commit()
        self.ip.create(kind='vlan',
                       ifname=ifV,
                       link=self.ip.interfaces[ifL].index,
                       vlan_id=101).commit()

        assert self.ip.interfaces[ifV].link == \
            self.ip.interfaces[ifL].index

    def test_remove_secondaries(self):
        require_user('root')

        ifA = self.get_ifname()

        with self.ip.create(kind='dummy', ifname=ifA) as i:
            i.add_ip('172.16.0.1', 24)
            i.add_ip('172.16.0.2', 24)

        assert ifA in self.ip.interfaces
        assert ('172.16.0.1', 24) in self.ip.interfaces[ifA].ipaddr
        assert ('172.16.0.2', 24) in self.ip.interfaces[ifA].ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface=ifA)
        assert '172.16.0.2/24' in get_ip_addr(interface=ifA)

        if i._mode == 'explicit':
            i.begin()

        i.del_ip('172.16.0.1', 24)
        i.del_ip('172.16.0.2', 24)
        i.commit()

        assert ('172.16.0.1', 24) not in self.ip.interfaces[ifA].ipaddr
        assert ('172.16.0.2', 24) not in self.ip.interfaces[ifA].ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface=ifA)
        assert '172.16.0.2/24' not in get_ip_addr(interface=ifA)


class TestImplicit(TestExplicit):
    mode = 'implicit'

    def test_chain(self):
        require_user('root')

        ifA = self.get_ifname()

        i = self.ip.create(ifname=ifA, kind='dummy')
        i.commit().up().commit()
        assert self.ip.interfaces[ifA].flags & 1

        i.add_ip('172.16.0.1/24').down().commit()
        assert ('172.16.0.1', 24) in self.ip.interfaces[ifA].ipaddr
        assert not (self.ip.interfaces[ifA].flags & 1)

        i.remove().commit()
        assert ifA not in self.ip.interfaces

    def test_generic_pre_callback(self):
        require_user('root')

        def cb(ipdb, msg, action):
            if action == 'RTM_NEWLINK':
                # fake the incoming message
                msg['flags'] = 1234

        ifA = self.get_ifname()
        # register callback
        self.ip.register_callback(cb, mode='pre')
        # create an interface bala
        self.ip.create(kind='dummy', ifname=ifA).commit()
        # assert flags
        assert self.ip.interfaces[ifA].flags == 1234
        # cleanup
        self.ip.unregister_callback(cb, mode='pre')
        self.ip.interfaces[ifA].remove()
        self.ip.interfaces[ifA].commit()

    def test_generic_post_callback(self):
        require_user('root')
        require_bridge()

        ifP1 = self.get_ifname()
        ifP2 = self.get_ifname()
        ifM = self.get_ifname()

        def cb(ipdb, msg, action):
            if action == 'RTM_NEWLINK' and \
                    msg.get_attr('IFLA_IFNAME', '') in (ifP1, ifP2):
                obj = ipdb.interfaces[msg['index']]
                ipdb.interfaces[ifM].add_port(obj)
                ipdb.interfaces[ifM].commit()

        wd0 = self.ip.watchdog(ifname=ifM)
        wd1 = self.ip.watchdog(ifname=ifP1)
        wd2 = self.ip.watchdog(ifname=ifP2)
        # create bridge
        self.ip.create(kind='bridge', ifname=ifM).commit()
        wd0.wait()
        # register callback
        self.ip.register_callback(cb)
        # create ports
        self.ip.create(kind='dummy', ifname=ifP1).commit()
        self.ip.create(kind='dummy', ifname=ifP2).commit()
        wd1.wait()
        wd2.wait()
        # check that ports are attached
        assert self.ip.interfaces[ifP1].index in \
            self.ip.interfaces[ifM].ports
        assert self.ip.interfaces[ifP2].index in \
            self.ip.interfaces[ifM].ports
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
        print("cfail done")

    def test_updown(self):
        require_user('root')

        assert not (self.ip.interfaces['dummyX'].flags & 1)
        self.ip.interfaces['dummyX'].up()

        assert self.ip.interfaces['dummyX'].flags & 1
        self.ip.interfaces['dummyX'].down()

        assert not (self.ip.interfaces['dummyX'].flags & 1)

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
            with ip.interfaces['dummyX'] as i:
                i.add_ip('172.16.0.1/24')

        try:
            with IPDB(mode='explicit') as ip:
                with ip.interfaces['dummyX'] as i:
                    i.add_ip('172.16.9.1/24')
                    i.del_ip('172.16.0.1/24')
                    i.address = '11:22:33:44:55:66'
        except NetlinkError:
            pass

        with IPDB() as ip:
            assert ('172.16.0.1', 24) in ip.interfaces['dummyX'].ipaddr
            assert ('172.16.9.1', 24) not in ip.interfaces['dummyX'].ipaddr

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
