# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import socket
import subprocess
from pyroute2 import config
from pyroute2 import IPDB
from pyroute2 import IPRoute
from pyroute2 import netns
from pyroute2 import NetNS
from pyroute2.common import basestring
from pyroute2.common import uifname
from pyroute2.ipdb.exceptions import CreateException
from pyroute2.ipdb.exceptions import PartialCommitException
from pyroute2.netlink.exceptions import NetlinkError
from utils import grep
from utils import create_link
from utils import kernel_version_ge
from utils import remove_link
from utils import require_user
from utils import require_8021q
from utils import get_ip_addr
from utils import skip_if_not_supported
from nose.plugins.skip import SkipTest


class _TestException(Exception):
    pass


class TestRace(object):

    def test_dummy0_unloaded(object):
        require_user('root')
        # firstly unload the dummy module
        with open(os.devnull, 'w') as fnull:
            subprocess.call(['modprobe', '-r', 'dummy'],
                            stdout=fnull,
                            stderr=fnull)
        ip = None
        try:
            # now create the dummy0 -- it will cause the
            # module autoload
            ip = IPDB()
            # that must succeed
            ip.create(ifname='dummy0', kind='dummy').commit()
            # just in case: the second attempt must fail on the
            # create() stage, even w/o any commit()
            try:
                ip.create(ifname='dummy0', kind='dummy')
            except CreateException:
                pass
        except Exception:
            raise
        finally:
            if ip is not None:
                ip.release()

    def test_dummy0_loaded(object):
        require_user('root')
        # assert the module is loaded
        ifA = uifname()
        ip = IPDB()
        ip.create(ifname=ifA, kind='dummy').commit()
        try:
            # try to create and fail in create()
            ip.create(ifname='dummy0', kind='dummy')
        except CreateException:
            pass
        except Exception:
            raise
        finally:
            ip.interfaces[ifA].remove().commit()
            ip.release()


class BasicSetup(object):
    ip = None
    mode = 'explicit'

    def setup(self):
        self.ifaces = []
        self.ifd = self.get_ifname()
        create_link(self.ifd, kind='dummy')
        self.ip = IPDB(mode=self.mode)

    def get_ifname(self):
        ifname = uifname()
        self.ifaces.append(ifname)
        return ifname

    def teardown(self):
        for name in self.ifaces:
            try:
                # just a hardcore removal
                self.ip.nl.link('del', index=self.ip.interfaces[name].index)
            except Exception:
                pass
        self.ip.release()
        self.ifaces = []


class TestExplicit(BasicSetup):

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

    def test_addr_attributes(self):
        require_user('root')

        if1 = self.get_ifname()
        if2 = self.get_ifname()

        with self.ip.create(ifname=if1, kind='dummy') as i:
            # +scope host (=> broadcast == None)
            i.add_ip('172.16.102.1/24', scope=254)

        with self.ip.create(ifname=if2, kind='dummy') as i:
            # +broadcast (default scope == 0)
            i.add_ip('172.16.103.1/24', broadcast='172.16.103.128')

        index = self.ip.interfaces[if1]['index']
        addr = self.ip.nl.get_addr(index=index)[0]
        assert addr['scope'] == 254
        assert addr.get_attr('IFA_BROADCAST') is None

        index = self.ip.interfaces[if2]['index']
        addr = self.ip.nl.get_addr(index=index)[0]
        assert addr['scope'] == 0
        assert addr.get_attr('IFA_BROADCAST') == '172.16.103.128'

    def test_addr_loaded(self):
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
        # test hasattr protocol
        assert hasattr(self.ip.interfaces, 'nonexistinginterface') is False

    @skip_if_not_supported
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
        assert len(r['+vlans']) == 0
        assert len(r['-vlans']) == 0
        assert len(r['+ports']) == 0
        assert len(r['-ports']) == 0
        # +/-ipaddr, +/-ports
        assert len([i for i in r if r[i] is not None]) == 6
        self.ip.interfaces.lo.drop()

    def test_review_new(self):
        i = self.ip.create(ifname='none', kind='dummy')
        i.add_ip('172.16.21.1/24')
        i.add_ip('172.16.21.2/24')
        i.add_port(self.ip.interfaces.lo)
        r = i.review()
        assert len(r['+ipaddr']) == 2
        assert len(r['+ports']) == 1
        assert '-ipaddr' not in r
        assert '-ports' not in r
        assert 'ipaddr' not in r
        assert 'ports' not in r

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

    @skip_if_not_supported
    def test_routes_mpls_metrics(self):
        require_user('root')
        self.ip.routes.add({'dst': 'default',
                            'table': 2020,
                            'gateway': '127.0.0.2',
                            'encap': {'type': 'mpls',
                                      'labels': '200'}}).commit()

        route = self.ip.routes.tables[2020]['default']
        with route:
            route.encap = {}
            route.metrics = {'mtu': 1320}

        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert not routes[0].get_attr('RTA_ENCAP')
        assert routes[0].get_attr('RTA_METRICS')

        with route:
            route.encap = {'type': 'mpls',
                           'labels': '700/800'}
        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert routes[0].get_attr('RTA_ENCAP')
        assert routes[0].get_attr('RTA_METRICS')

        with route:
            route.encap = {}
            route.metrics = {}
        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert not routes[0].get_attr('RTA_ENCAP')
        assert not routes[0].get_attr('RTA_METRICS')

        with route:
            route.remove()

    @skip_if_not_supported
    def test_routes_mpls(self):
        require_user('root')
        self.ip.routes.add({'dst': 'default',
                            'table': 2020,
                            'gateway': '127.0.0.2',
                            'encap': {'type': 'mpls',
                                      'labels': '200'}}).commit()
        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert routes[0].get_attr('RTA_GATEWAY') == '127.0.0.2'
        encap = (routes[0]
                 .get_attr('RTA_ENCAP')
                 .get_attr('MPLS_IPTUNNEL_DST'))
        assert len(encap) == 1
        assert encap[0]['label'] == 200
        assert encap[0]['bos'] == 1

        assert len(self.ip.routes.tables[2020]) == 1
        route = self.ip.routes.tables[2020]['default']
        assert route['table'] == 2020
        assert route['encap']['labels'] == '200'
        assert route['gateway'] == '127.0.0.2'
        assert route['oif'] and route['oif'] > 0

        with route:
            route.remove()

    @skip_if_not_supported
    def test_routes_mpls_change(self):
        require_user('root')
        self.ip.routes.add({'dst': 'default',
                            'table': 2020,
                            'gateway': '127.0.0.2',
                            'encap': {'type': 'mpls',
                                      'labels': '200'}}).commit()
        assert 2020 in self.ip.routes.tables.keys()
        assert len(self.ip.routes.tables[2020]) == 1
        route = self.ip.routes.tables[2020]['default']
        assert route['encap']['labels'] == '200'

        with route:
            route['encap']['labels'] = '200/300'
        assert len(self.ip.routes.tables[2020]) == 1

        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert routes[0].get_attr('RTA_GATEWAY') == '127.0.0.2'
        encap = (routes[0]
                 .get_attr('RTA_ENCAP')
                 .get_attr('MPLS_IPTUNNEL_DST'))
        assert len(encap) == 2
        assert encap[0]['label'] == 200
        assert encap[0]['bos'] == 0
        assert encap[1]['label'] == 300
        assert encap[1]['bos'] == 1

        with route:
            route['encap'] = {'type': 'mpls',
                              'labels': '500/600'}
        assert len(self.ip.routes.tables[2020]) == 1

        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert routes[0].get_attr('RTA_GATEWAY') == '127.0.0.2'
        encap = (routes[0]
                 .get_attr('RTA_ENCAP')
                 .get_attr('MPLS_IPTUNNEL_DST'))
        assert len(encap) == 2
        assert encap[0]['label'] == 500
        assert encap[0]['bos'] == 0
        assert encap[1]['label'] == 600
        assert encap[1]['bos'] == 1

        with route:
            route['encap'] = {}
        assert len(self.ip.routes.tables[2020]) == 1

        routes = self.ip.nl.get_routes(table=2020)
        assert len(routes) == 1
        assert routes[0].get_attr('RTA_GATEWAY') == '127.0.0.2'
        assert not routes[0].get_attr('RTA_ENCAP')

        with route:
            route.remove()

    def test_routes_type(self):
        require_user('root')
        self.ip.routes.add(dst='default',
                           table=202,
                           type='unreachable').commit()
        self.ip.routes.add(dst='default',
                           table=2020,
                           type='blackhole').commit()
        assert grep('ip ro show table 202',
                    pattern='unreachable default')
        assert grep('ip ro show table 2020',
                    pattern='blackhole default')
        with self.ip.routes.tables[202]['default'] as r:
            r.remove()
        with self.ip.routes.tables[2020]['default'] as r:
            r.remove()

    def test_routes_keys(self):
        assert '172.16.0.0/24' not in self.ip.routes
        # create but not commit
        self.ip.routes.add(dst='172.16.0.0/24', gateway='127.0.0.1')
        # checks
        assert '172.16.0.0/24' in self.ip.routes
        assert '172.16.0.0/24' in list(self.ip.routes.keys())

    def test_routes_proto(self):
        require_user('root')
        assert '172.16.2.0/24' not in self.ip.routes
        assert '172.16.3.0/24' not in self.ip.routes
        os.system('ip route add 172.16.2.0/24 via 127.0.0.1')  # proto boot
        os.system('ip route add 172.16.3.0/24 via 127.0.0.1 proto static')

        time.sleep(1)

        assert grep('ip ro', pattern='172.16.2.0/24.*127.0.0.1')
        with self.ip.routes['172.16.2.0/24'] as r:
            r.remove()
        assert not grep('ip ro', pattern='172.16.2.0/24.*127.0.0.1')

        assert grep('ip ro', pattern='172.16.3.0/24.*127.0.0.1')
        with self.ip.routes['172.16.3.0/24'] as r:
            r.remove()
        assert not grep('ip ro', pattern='172.16.3.0/24.*127.0.0.1')

    def test_routes(self):
        require_user('root')
        assert '172.16.0.0/24' not in self.ip.routes

        # create a route
        with self.ip.routes.add({'dst': '172.16.0.0/24',
                                 'gateway': '127.0.0.1'}) as r:
            pass
        assert '172.16.0.0/24' in self.ip.routes.keys()
        assert grep('ip ro', pattern='172.16.0.0/24.*127.0.0.1')

        # change the route
        with self.ip.routes['172.16.0.0/24'] as r:
            r.gateway = '127.0.0.2'
        assert self.ip.routes['172.16.0.0/24'].gateway == '127.0.0.2'
        assert grep('ip ro', pattern='172.16.0.0/24.*127.0.0.2')

        # delete the route
        with self.ip.routes['172.16.0.0/24'] as r:
            r.remove()
        assert '172.16.0.0/24' not in self.ip.routes.keys()
        assert not grep('ip ro', pattern='172.16.0.0/24')

    def test_routes_multipath_gateway(self):
        require_user('root')
        ifR = self.get_ifname()

        with self.ip.create(ifname=ifR, kind='dummy') as i:
            i.add_ip('172.16.231.1/24')
            i.up()

        r = self.ip.routes.add({'dst': '172.16.232.0/24',
                                'multipath': [{'gateway': '172.16.231.2',
                                               'hops': 20},
                                              {'gateway': '172.16.231.3',
                                               'hops': 30},
                                              {'gateway': '172.16.231.4'}]})
        r.commit()
        assert grep('ip ro', pattern='172.16.232.0/24')
        assert grep('ip ro', pattern='nexthop.*172.16.231.2.*weight.*21')
        assert grep('ip ro', pattern='nexthop.*172.16.231.3.*weight.*31')
        assert grep('ip ro', pattern='nexthop.*172.16.231.4.*weight.*1')

        with self.ip.routes['172.16.232.0/24'] as r:
            r.add_nh({'gateway': '172.16.231.5', 'hops': 50})
            r.del_nh({'gateway': '172.16.231.2'})
        assert grep('ip ro', pattern='172.16.232.0/24')
        assert grep('ip ro', pattern='nexthop.*172.16.231.5.*weight.*51')
        assert grep('ip ro', pattern='nexthop.*172.16.231.3.*weight.*31')
        assert grep('ip ro', pattern='nexthop.*172.16.231.4.*weight.*1')

    def test_routes_metrics(self):
        require_user('root')
        assert '172.16.0.0/24' not in self.ip.routes.keys()

        # create a route
        self.ip.routes.add({'dst': '172.16.0.0/24',
                            'gateway': '127.0.0.1',
                            'metrics': {'mtu': 1360}}).commit()
        assert grep('ip ro', pattern='172.16.0.0/24.*mtu 1360')

        # change metrics
        with self.ip.routes['172.16.0.0/24'] as r:
            r.metrics.mtu = 1400
        assert self.ip.routes['172.16.0.0/24']['metrics']['mtu'] == 1400
        assert grep('ip ro', pattern='172.16.0.0/24.*mtu 1400')

        # delete the route
        with self.ip.routes['172.16.0.0/24'] as r:
            r.remove()

        assert '172.16.0.0/24' not in self.ip.routes.keys()
        assert not grep('ip ro', pattern='172.16.0.0/24')

    def test_wait_ip_exact(self):
        ts = time.time()
        ret = self.ip.interfaces.lo.wait_ip('127.0.0.1', timeout=2)
        assert (time.time() - ts) < 2
        assert ret

    def test_wait_ip_net(self):
        ts = time.time()
        ret = self.ip.interfaces.lo.ipaddr.wait_ip('127.0.0.0', 8, timeout=2)
        assert (time.time() - ts) < 2
        assert ret

    def test_wait_ip_exact_fail(self):
        ts = time.time()
        ret = self.ip.interfaces.lo.wait_ip('1.1.1.1', timeout=2)
        assert (time.time() - ts) >= 2
        assert not ret

    def test_wait_ip_net_fail(self):
        ts = time.time()
        ret = self.ip.interfaces.lo.ipaddr.wait_ip('172.6.0.0', 24, timeout=2)
        assert (time.time() - ts) >= 2
        assert not ret

    @skip_if_not_supported
    def _test_shadow(self, kind):
        ifA = self.get_ifname()

        a = self.ip.create(ifname=ifA, kind=kind).commit()
        if a._mode == 'explicit':
            a.begin()
        a.shadow().commit()
        assert ifA in self.ip.interfaces
        assert not grep('ip link', pattern=ifA)
        time.sleep(0.5)
        b = self.ip.create(ifname=ifA, kind=kind).commit()
        assert a == b
        assert grep('ip link', pattern=ifA)

    def test_shadow_bond(self):
        require_user('root')
        self._test_shadow('bond')

    def test_shadow_bridge(self):
        require_user('root')
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

    def test_slave_data(self):
        require_user('root')

        ifBR = self.get_ifname()
        ifP = self.get_ifname()
        self.ip.debug = True

        bridge = self.ip.create(ifname=ifBR, kind='bridge').commit()
        port = self.ip.create(ifname=ifP, kind='dummy').commit()

        if self.ip.mode == 'explicit':
            bridge.begin()
        bridge.add_port(port)
        bridge.up()
        bridge.commit()

        li = port.nlmsg.get_attr('IFLA_LINKINFO')
        skind = li.get_attr('IFLA_INFO_SLAVE_KIND')
        sdata = li.get_attr('IFLA_INFO_SLAVE_DATA')
        self.ip.debug = False
        if skind is None or sdata is None:
            raise SkipTest('slave data not provided')

        assert sdata.get_attr('IFLA_BRPORT_STATE') is not None
        assert sdata.get_attr('IFLA_BRPORT_MODE') is not None

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

    def test_multiple_ips_one_transaction(self):
        require_user('root')

        ifA = self.get_ifname()
        with self.ip.create(kind='dummy', ifname=ifA) as i:
            for x in range(1, 255):
                i.add_ip('172.16.0.%i/24' % x)
            i.up()

        idx = self.ip.interfaces[ifA].index
        assert len(self.ip.nl.get_addr(index=idx, family=2)) == 254

    def test_json_dump(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        # set up the interface
        with self.ip.create(kind='dummy', ifname=ifA) as i:
            i.add_ip('172.16.0.1/24')
            i.up()

        # imitate some runtime
        time.sleep(2)

        # make a backup
        backup = self.ip.interfaces[ifA].dump()
        assert isinstance(backup, dict)

        # remove index and protinfo -- make it portable
        del backup['index']
        if 'protinfo' in backup:
            del backup['protinfo']

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
        with self.ip.interfaces[ifB] as i:
            i.load(json.loads(backup))

        # check :)
        assert ifA in self.ip.interfaces
        assert ifB not in self.ip.interfaces
        for ipaddr in json.loads(backup)['ipaddr']:
            assert tuple(ipaddr) in self.ip.interfaces[ifA].ipaddr
        assert self.ip.interfaces[ifA].flags & 1

    def test_freeze_del(self):
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

        interface.freeze()

        # delete interface with an external routine
        remove_link(interface.ifname)

        # wait for a second
        time.sleep(1)

        # check if it is back
        ipdb = IPDB()
        try:
            ifc = ipdb.interfaces[self.ifd]
            assert ('172.16.0.1', 24) in ifc.ipaddr
            assert ('172.16.1.1', 24) in ifc.ipaddr
            assert ifc.flags & 1
        except:
            raise
        finally:
            interface.unfreeze()
            ipdb.release()

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
                i2.close()
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
            i2.close()

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

    @skip_if_not_supported
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

    def test_create_ip_up(self):
        require_user('root')
        ifA = self.get_ifname()
        with self.ip.create(ifname=ifA, kind='dummy') as i:
            i.up()
            i.add_ip('172.16.7.8/24')
        assert ifA in self.ip.interfaces
        assert ('172.16.7.8', 24) in self.ip.interfaces[ifA].ipaddr

    @skip_if_not_supported
    def test_create_tuntap_fail(self):
        try:
            self.ip.create(ifname='fAiL',
                           kind='tuntap',
                           mode='fail').commit()
        except:
            assert not grep('ip link', pattern='fAiL')
            return
        raise Exception('tuntap create succeded')

    @skip_if_not_supported
    def test_create_tuntap(self):
        require_user('root')

        ifA = self.get_ifname()
        self.ip.create(ifname=ifA,
                       kind='tuntap',
                       mode='tap',
                       uid=1,
                       gid=1).commit()

        assert ifA in self.ip.interfaces
        assert grep('ip link', pattern=ifA)

    def test_global_create(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()
        self.ip.create(ifname=ifA, kind='dummy')
        self.ip.create(ifname=ifB, kind='dummy')
        self.ip.commit()

        assert ifA in self.ip.interfaces
        assert ifB in self.ip.interfaces
        assert grep('ip link', pattern=ifA)
        assert grep('ip link', pattern=ifB)

    def test_global_priorities(self):
        require_user('root')
        ifA = self.get_ifname()
        ifB = self.get_ifname()
        ifC = self.get_ifname()
        a = self.ip.create(ifname=ifA, kind='dummy').commit()
        #
        if a._mode == 'explicit':
            a.begin()

        # prepare transaction: two interface creations
        # and one failure on an existing interface
        a.set_address('11:22:33:44:55:66')
        b = self.ip.create(ifname=ifB, kind='dummy')
        c = self.ip.create(ifname=ifC, kind='dummy')
        # now assign priorities
        b.ipdb_priority = 15  # will be execute first
        a.ipdb_priority = 10  # second -- and fail
        c.ipdb_priority = 5   # should not be executed
        # prepare watchdogs
        wdb = self.ip.watchdog(ifname=ifB)
        wdc = self.ip.watchdog(ifname=ifC)
        # run the transaction
        try:
            self.ip.commit()
        except NetlinkError:
            pass
        # control system state
        assert ifA in self.ip.interfaces
        assert ifB in self.ip.interfaces
        assert ifC in self.ip.interfaces
        assert a.ipdb_scope == 'system'
        assert b.ipdb_scope == 'create'
        assert c.ipdb_scope == 'create'
        assert a.address != '11:22:33:44:55:66'
        assert grep('ip link', pattern=ifA)
        assert not grep('ip link', pattern=ifB)
        assert not grep('ip link', pattern=ifC)
        wdb.wait(1)
        wdc.wait(1)
        assert wdb.is_set
        assert not wdc.is_set

    def test_global_rollback(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()
        a = self.ip.create(ifname=ifA, kind='dummy').commit()
        #
        if a._mode == 'explicit':
            a.begin()
        a.remove()
        b = self.ip.create(ifname=ifB, kind='dummy')
        b.set_mtu(1500).set_address('11:22:33:44:55:66')
        try:
            self.ip.commit()
        except NetlinkError:
            pass

        assert ifA in self.ip.interfaces
        assert ifB in self.ip.interfaces
        assert b.ipdb_scope == 'create'
        assert grep('ip link', pattern=ifA)
        assert not grep('ip link', pattern=ifB)

    def test_bridge_vlans_flags(self):
        require_user('root')
        ifB = self.get_ifname()
        ifP = self.get_ifname()
        b = self.ip.create(ifname=ifB, kind='bridge').commit()
        p = self.ip.create(ifname=ifP, kind='dummy').commit()
        assert len(p.vlans) == 0

        with b:
            b.add_port(p)

        with p:
            p.add_vlan({'vid': 202, 'flags': 6})
            p.add_vlan({'vid': 204, 'flags': 0})
            p.add_vlan(206)
        assert p.vlans == set((1, 202, 204, 206))
        assert p.vlans[202]['flags'] == 6
        assert p.vlans[204]['flags'] == 0
        assert p.vlans[206]['flags'] == 0

    def test_bridge_vlans(self):
        require_user('root')
        ifB = self.get_ifname()
        ifP = self.get_ifname()
        b = self.ip.create(ifname=ifB, kind='bridge').commit()
        p = self.ip.create(ifname=ifP, kind='dummy').commit()
        assert len(p.vlans) == 0

        with b:
            b.add_port(p)
        assert len(p.vlans) == 1

        with p:
            p.add_vlan(202)
            p.add_vlan(204)
            p.add_vlan(206)
        assert p.vlans == set((1, 202, 204, 206))

        with p:
            p.del_vlan(204)
        assert p.vlans == set((1, 202, 206))

        with b:
            b.del_port(p)
        assert len(p.vlans) == 0

    def test_veth_peer_attrs(self):
        require_user('root')

        ifA = self.get_ifname()
        ns = str(uuid.uuid4())

        addr_ext = '06:00:00:00:02:02'
        addr_int = '06:00:00:00:02:03'

        with IPDB(nl=NetNS(ns)) as nsdb:
            veth = self.ip.create(**{'ifname': 'x' + ifA,
                                     'kind': 'veth',
                                     'address': addr_ext,
                                     'peer': {'ifname': ifA,
                                              'address': addr_int,
                                              'net_ns_fd': ns}})
            veth.commit()
            assert nsdb.interfaces[ifA]['address'] == addr_int
            assert self.ip.interfaces['x' + ifA]['address'] == addr_ext

            with veth:
                veth.remove()

        netns.remove(ns)

    def test_global_netns(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()
        ns = str(uuid.uuid4())

        with IPDB(nl=NetNS(ns)) as nsdb:
            v1 = self.ip.create(ifname='x' + ifA, kind='veth', peer=ifA)
            v2 = self.ip.create(ifname='x' + ifB, kind='veth', peer=ifB)
            if v1._mode == 'explicit':
                v1.begin()
                v2.begin()
            v1.net_ns_fd = ns
            v2.net_ns_fd = ns
            self.ip.commit()
            nsdb.interfaces['x' + ifA].ifname = 'eth0'
            nsdb.interfaces['x' + ifB].ifname = 'eth1'
            nsdb.commit()
            if self.ip.interfaces[ifA]._mode == 'explicit':
                self.ip.interfaces[ifA].begin()
                self.ip.interfaces[ifB].begin()
            self.ip.interfaces[ifA].up()
            self.ip.interfaces[ifB].up()
            self.ip.commit()

        assert 'x' + ifA not in self.ip.interfaces
        assert 'x' + ifB not in self.ip.interfaces
        assert ifA in self.ip.interfaces
        assert ifB in self.ip.interfaces
        assert self.ip.interfaces[ifA].flags & 1
        assert self.ip.interfaces[ifB].flags & 1

        if self.ip.interfaces[ifA]._mode == 'explicit':
            self.ip.interfaces[ifA].begin()
            self.ip.interfaces[ifB].begin()
        self.ip.interfaces[ifA].remove()
        self.ip.interfaces[ifB].remove()
        self.ip.commit()
        netns.remove(ns)

    @skip_if_not_supported
    def test_create_veth(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        self.ip.create(ifname=ifA, kind='veth', peer=ifB).commit()

        assert ifA in self.ip.interfaces
        assert ifB in self.ip.interfaces

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

    def test_create_reuse_addr(self):
        require_user('root')

        ifA = self.get_ifname()
        with self.ip.create(kind='dummy', ifname=ifA) as i:
            i.add_ip('172.16.47.2/24')
            i.down()
        assert ('172.16.47.2', 24) in self.ip.interfaces[ifA].ipaddr
        assert not self.ip.interfaces[ifA].flags & 1
        with IPDB() as ip:
            with ip.create(kind='dummy', ifname=ifA, reuse=True) as i:
                i.up()
            assert ('172.16.47.2', 24) in ip.interfaces[ifA].ipaddr
            assert ip.interfaces[ifA].flags & 1
        assert self.ip.interfaces[ifA].flags & 1

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

    @skip_if_not_supported
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

    def test_dqn_mask(self):
        require_user('root')

        iface = self.ip.interfaces[self.ifd]
        with iface as i:
            i.add_ip('172.16.0.1/24')
            i.add_ip('172.16.0.2', mask=24)
            i.add_ip('172.16.0.3/255.255.255.0')
            i.add_ip('172.16.0.4', mask='255.255.255.0')

        assert ('172.16.0.1', 24) in iface.ipaddr
        assert ('172.16.0.2', 24) in iface.ipaddr
        assert ('172.16.0.3', 24) in iface.ipaddr
        assert ('172.16.0.4', 24) in iface.ipaddr

    @skip_if_not_supported
    def test_master_cleanup_del_port(self):
        require_user('root')

        ifMname = self.get_ifname()
        ifPname = self.get_ifname()

        ifM = self.ip.create(ifname=ifMname, kind='bridge').commit()
        ifP = self.ip.create(ifname=ifPname, kind='dummy').commit()

        if self.ip.mode == 'explicit':
            ifM.begin()
        ifM.\
            add_port(ifP).\
            commit()

        assert ifP.index in ifM.ports
        assert ifP.master == ifM.index

        if self.ip.mode == 'explicit':
            ifM.begin()
        ifM.del_port(ifP).commit()

        assert ifPname in self.ip.interfaces
        assert ifP.index not in ifM.ports
        assert ifP.master is None

    @skip_if_not_supported
    def _create_master(self, kind, **kwarg):

        ifM = self.get_ifname()
        ifP1 = self.get_ifname()
        ifP2 = self.get_ifname()

        self.ip.create(kind='dummy', ifname=ifP1).commit()
        self.ip.create(kind='dummy', ifname=ifP2).commit()

        with self.ip.create(kind=kind, ifname=ifM, **kwarg) as i:
            i.add_port(self.ip.interfaces[ifP1])
            i.add_ip('172.16.0.1/24')

        with self.ip.interfaces[ifM] as i:
            i.add_port(self.ip.interfaces[ifP2])
            i.add_ip('172.16.0.2/24')

        assert ('172.16.0.1', 24) in self.ip.interfaces[ifM].ipaddr
        assert ('172.16.0.2', 24) in self.ip.interfaces[ifM].ipaddr
        assert '172.16.0.1/24' in get_ip_addr(interface=ifM)
        assert '172.16.0.2/24' in get_ip_addr(interface=ifM)
        assert self.ip.interfaces[ifP1].if_master == \
            self.ip.interfaces[ifM].index
        assert self.ip.interfaces[ifP2].if_master == \
            self.ip.interfaces[ifM].index

        with self.ip.interfaces[ifM] as i:
            i.del_port(self.ip.interfaces[ifP1])
            i.del_port(self.ip.interfaces[ifP2])
            i.del_ip('172.16.0.1/24')
            i.del_ip('172.16.0.2/24')

        assert ('172.16.0.1', 24) not in self.ip.interfaces[ifM].ipaddr
        assert ('172.16.0.2', 24) not in self.ip.interfaces[ifM].ipaddr
        assert '172.16.0.1/24' not in get_ip_addr(interface=ifM)
        assert '172.16.0.2/24' not in get_ip_addr(interface=ifM)
        assert self.ip.interfaces[ifP1].if_master is None
        assert self.ip.interfaces[ifP2].if_master is None

    def test_create_bridge(self):
        require_user('root')
        self._create_master('bridge')

    def test_create_bond(self):
        require_user('root')
        self._create_master('bond')

    def test_create_team(self):
        require_user('root')
        self._create_master('team')

    def test_create_bond2(self):
        require_user('root')
        self._create_master('bond', bond_mode=2)

    @skip_if_not_supported
    def _create_macvx_mode(self, kind, mode):
        require_user('root')
        ifL = self.get_ifname()
        ifV = self.get_ifname()
        ifdb = self.ip.interfaces

        self.ip.create(kind='dummy',
                       ifname=ifL).commit()
        self.ip.create(**{'kind': kind,
                          'link': ifdb[ifL],
                          'ifname': ifV,
                          '%s_mode' % kind: mode}).commit()

        ip2 = IPDB()
        ifdb = ip2.interfaces
        try:
            assert ifdb[ifV]['kind'] == kind
            assert ifdb[ifV].link == ifdb[ifL].index
            assert ifdb[ifV]['%s_mode' % kind] == mode
        except Exception:
            raise
        finally:
            ip2.release()

    def test_create_macvtap_vepa(self):
        return self._create_macvx_mode('macvtap', 'vepa')

    def test_create_macvtap_bridge(self):
        return self._create_macvx_mode('macvtap', 'bridge')

    def test_create_macvlan_vepa(self):
        return self._create_macvx_mode('macvlan', 'vepa')

    def test_create_macvlan_bridge(self):
        return self._create_macvx_mode('macvlan', 'bridge')

    def test_create_utf_name(self):
        require_user('root')
        ifO = 'ༀ'
        self.ip.create(kind='dummy', ifname=ifO).commit()
        assert ifO in self.ip.interfaces
        assert self.ip.nl.link_lookup(ifname=ifO)
        if self.ip.interfaces[ifO]._mode == 'explicit':
            self.ip.interfaces[ifO].begin()
        self.ip.interfaces[ifO].remove().commit()

    @skip_if_not_supported
    def test_create_gre(self):
        require_user('root')

        ifL = self.get_ifname()
        ifV = self.get_ifname()
        with self.ip.create(kind='dummy', ifname=ifL) as i:
            i.add_ip('172.16.0.1/24')
            i.up()

        self.ip.create(kind='gre',
                       ifname=ifV,
                       gre_local='172.16.0.1',
                       gre_remote='172.16.0.2',
                       gre_ttl=16).commit()

        ip2 = IPDB()
        ifdb = ip2.interfaces
        try:
            assert ifdb[ifV].gre_local == '172.16.0.1'
            assert ifdb[ifV].gre_remote == '172.16.0.2'
            assert ifdb[ifV].gre_ttl == 16
        except Exception:
            raise
        finally:
            ip2.release()

    @skip_if_not_supported
    def test_create_gretap(self):
        require_user('root')

        ifL = self.get_ifname()
        ifV = self.get_ifname()
        with self.ip.create(kind='dummy', ifname=ifL) as i:
            i.add_ip('172.16.0.1/24')
            i.up()

        self.ip.create(kind='gretap',
                       ifname=ifV,
                       gre_local='172.16.0.1',
                       gre_ikey=1,
                       gre_okey=2,
                       gre_iflags=0x0020,
                       gre_oflags=0x0020,
                       gre_collect_metadata=True,
                       gre_ttl=16).commit()

        ip2 = IPDB()
        ifdb = ip2.interfaces
        try:
            assert ifdb[ifV].gre_local == '172.16.0.1'
            assert ifdb[ifV].gre_ikey == 1
            assert ifdb[ifV].gre_okey == 2
            assert ifdb[ifV].gre_iflags == 0x0020
            assert ifdb[ifV].gre_oflags == 0x0020
            if kernel_version_ge(4, 3):
                assert ifdb[ifV].gre_collect_metadata
            assert ifdb[ifV].gre_ttl == 16
        except Exception:
            raise
        finally:
            ip2.release()

    @skip_if_not_supported
    def test_create_vxlan(self):
        require_user('root')

        ifL = self.get_ifname()
        ifV = self.get_ifname()
        ifdb = self.ip.interfaces

        self.ip.create(kind='dummy',
                       ifname=ifL).commit()
        self.ip.create(kind='vxlan',
                       ifname=ifV,
                       vxlan_link=ifdb[ifL],
                       vxlan_id=101,
                       vxlan_group='239.1.1.1').commit()

        ip2 = IPDB()
        ifdb = ip2.interfaces

        try:
            assert ifdb[ifV].vxlan_link == ifdb[ifL].index
            assert ifdb[ifV].vxlan_group == '239.1.1.1'
            assert ifdb[ifV].vxlan_id == 101
        except Exception:
            raise
        finally:
            ip2.release()

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


class TestCompat(TestExplicit):

    def setup(self):
        TestExplicit.setup(self)
        self.caps = self.ip.nl.capabilities
        self.ip.nl.capabilities = {'create_dummy': True,
                                   'create_bridge': False,
                                   'create_bond': False,
                                   'provide_master': False}
        config.kernel = [2, 6, 32]  # RHEL 6


class TestPartial(BasicSetup):
    mode = 'implicit'

    def test_delay_port(self):
        require_user('root')
        ifB = self.get_ifname()
        ifBp0 = self.get_ifname()
        ifBp1 = self.get_ifname()

        b = self.ip.create(ifname=ifB, kind='bridge').commit()
        bp0 = self.ip.create(ifname=ifBp0, kind='dummy').commit()

        b.add_port(ifBp0)
        b.add_port(ifBp1)
        t = b.last()
        t.partial = True
        try:
            b.commit(transaction=t)
        except PartialCommitException:
            pass

        assert len(b['ports']) == 1
        assert bp0['index'] in b['ports']
        assert len(t.errors) == 1

        bp1 = self.ip.create(ifname=ifBp1, kind='dummy').commit()
        b.commit(transaction=t)

        assert len(b['ports']) == 2
        assert bp1['index'] in b['ports']
        assert len(t.errors) == 0


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
        cuid = self.ip.register_callback(cb, mode='pre')
        # create an interface bala
        self.ip.create(kind='dummy', ifname=ifA).commit()
        # assert flags
        assert self.ip.interfaces[ifA].flags == 1234
        # cleanup
        self.ip.unregister_callback(cuid, mode='pre')
        self.ip.interfaces[ifA].remove()
        self.ip.interfaces[ifA].commit()

    @skip_if_not_supported
    def test_generic_post_callback(self):
        require_user('root')

        ifP1 = self.get_ifname()
        ifP2 = self.get_ifname()
        ifM = self.get_ifname()

        def cb(ipdb, msg, action):
            if action == 'RTM_NEWLINK' and \
                    msg.get_attr('IFLA_IFNAME', '') in (ifP1, ifP2):
                obj = ipdb.interfaces[msg['index']]
                if obj not in ipdb.interfaces[ifM]:
                    ipdb.interfaces[ifM].add_port(obj)
                try:
                    ipdb.interfaces[ifM].commit()
                except Exception:
                    pass

        wd0 = self.ip.watchdog(ifname=ifM)
        # create bridge
        m = self.ip.create(kind='bridge', ifname=ifM).commit()
        wd0.wait()
        # register callback
        cuid = self.ip.register_callback(cb)
        # create ports
        wd1 = self.ip.watchdog(ifname=ifP1, master=m.index)
        wd2 = self.ip.watchdog(ifname=ifP2, master=m.index)
        self.ip.create(kind='dummy', ifname=ifP1).commit()
        self.ip.create(kind='dummy', ifname=ifP2).commit()
        wd1.wait()
        wd2.wait()
        # FIXME: wait some time for DB to stabilize
        time.sleep(0.5)
        # check that ports are attached
        assert self.ip.interfaces[ifP1].index in \
            self.ip.interfaces[ifM].ports
        assert self.ip.interfaces[ifP2].index in \
            self.ip.interfaces[ifM].ports
        # unregister callback
        self.ip.unregister_callback(cuid)


class TestDirect(object):

    def setup(self):
        self.ifname = uifname()
        self.ip = IPDB(mode='direct')
        try:
            self.ip.create(ifname=self.ifname, kind='dummy')
        except:
            pass

    def teardown(self):
        try:
            self.ip.interfaces[self.ifname].remove()
        except KeyError:
            pass
        self.ip.release()

    def test_context_fail(self):
        require_user('root')
        try:
            with self.ip.interfaces[self.ifname] as i:
                i.down()
        except TypeError:
            pass

    def test_create(self):
        require_user('root')
        ifname = uifname()
        assert ifname not in self.ip.interfaces
        self.ip.create(ifname=ifname, kind='dummy')
        assert ifname in self.ip.interfaces
        self.ip.interfaces[ifname].remove()
        assert ifname not in self.ip.interfaces

    def test_updown(self):
        require_user('root')

        assert not (self.ip.interfaces[self.ifname].flags & 1)
        self.ip.interfaces[self.ifname].up()

        assert self.ip.interfaces[self.ifname].flags & 1
        self.ip.interfaces[self.ifname].down()

        assert not (self.ip.interfaces[self.ifname].flags & 1)

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
        self.ifname = uifname()
        create_link(self.ifname, 'dummy')

    def teardown(self):
        remove_link(self.ifname)

    def test_commit_barrier(self):
        require_user('root')

        ifname = uifname()

        # barrier 0
        try:
            ip = IPDB()
            config.commit_barrier = 0
            ts1 = time.time()
            ip.create(ifname=ifname, kind='dummy').commit()
            ts2 = time.time()
            assert 0 < (ts2 - ts1) < 1
        except:
            raise
        finally:
            config.commit_barrier = 0.2
            ip.interfaces[ifname].remove().commit()
            ip.release()

        # barrier 5
        try:
            ip = IPDB()
            config.commit_barrier = 5
            ts1 = time.time()
            ip.create(ifname=ifname, kind='dummy').commit()
            ts2 = time.time()
            assert 5 < (ts2 - ts1) < 6
        except:
            raise
        finally:
            config.commit_barrier = 0.2
            ip.interfaces[ifname].remove().commit()
            ip.release()

    def test_fail_released(self):
        ip = IPDB()
        ip.release()
        assert len(ip.interfaces.keys()) == 0

    def test_fail_initdb(self):

        # mock class
        class MockNL(object):

            def __init__(self):
                self.called = set()

            def bind(self, async=False):
                self.called.add('bind')
                assert async in (True, False)
                raise NotImplementedError('mock thee')

            def close(self):
                self.called.add('close')
                raise NotImplementedError('mock thee')

        mnl = MockNL()
        try:
            IPDB(nl=mnl)
        except NotImplementedError:
            pass

        assert mnl.called == set(('bind', 'close'))

    def test_context_manager(self):
        with IPDB() as ip:
            assert ip.interfaces.lo.index == 1

    def test_context_exception_in_code(self):
        require_user('root')
        try:
            with IPDB(mode='explicit') as ip:
                with ip.interfaces[self.ifname] as i:
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
            assert ('172.16.9.1', 24) not in ip.interfaces[self.ifname].ipaddr

    def test_context_exception_in_transaction(self):
        require_user('root')

        with IPDB(mode='explicit') as ip:
            with ip.interfaces[self.ifname] as i:
                i.add_ip('172.16.0.1/24')

        try:
            with IPDB(mode='explicit') as ip:
                with ip.interfaces[self.ifname] as i:
                    i.add_ip('172.16.9.1/24')
                    i.del_ip('172.16.0.1/24')
                    i.address = '11:22:33:44:55:66'
        except NetlinkError:
            pass

        with IPDB() as ip:
            assert ('172.16.0.1', 24) in ip.interfaces[self.ifname].ipaddr
            assert ('172.16.9.1', 24) not in ip.interfaces[self.ifname].ipaddr

    def test_ipaddr_format(self):

        with IPDB() as i:
            for addr in i.interfaces.lo.ipaddr:
                assert isinstance(addr[0], basestring)
                assert isinstance(addr[1], int)

    def test_ignore_rtables_int(self):
        with IPDB(ignore_rtables=255) as i:
            assert 254 in i.routes.tables.keys()
            assert 255 not in i.routes.tables.keys()

    def test_ignore_rtables_list(self):
        with IPDB(ignore_rtables=[0, 255]) as i:
            assert 254 in i.routes.tables.keys()
            assert 0 not in i.routes.tables.keys()
            assert 255 not in i.routes.tables.keys()

    def test_modes(self):
        require_user('root')
        with IPDB(mode='explicit') as i:
            # transaction required
            try:
                i.interfaces[self.ifname].up()
            except TypeError:
                pass

        with IPDB(mode='implicit') as i:
            # transaction aut-begin()
            assert len(i.interfaces[self.ifname]._tids) == 0
            i.interfaces[self.ifname].up()
            assert len(i.interfaces[self.ifname]._tids) == 1
            i.interfaces[self.ifname].drop()
            assert len(i.interfaces[self.ifname]._tids) == 0

        with IPDB(mode='invalid') as i:
            # transaction mode not supported
            try:
                i.interfaces[self.ifname].up()
            except TypeError:
                pass
