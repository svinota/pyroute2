# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import random
import socket
import threading
import subprocess
from pyroute2 import config
from pyroute2 import IPDB
from pyroute2 import IPRoute
from pyroute2 import netns
from pyroute2 import NetNS
from pyroute2.common import basestring
from pyroute2.common import uifname
from pyroute2.common import AF_MPLS
from pyroute2.ipdb.exceptions import CreateException
from pyroute2.ipdb.exceptions import PartialCommitException
from pyroute2.netlink.exceptions import NetlinkError
from utils import grep
from utils import create_link
from utils import kernel_version_ge
from utils import remove_link
from utils import require_user
from utils import require_8021q
from utils import require_kernel
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
    sort_addresses = True

    def setup(self):
        self.ifaces = []
        self.ifd = self.get_ifname()
        create_link(self.ifd, kind='dummy')
        self.ip = IPDB(mode=self.mode, sort_addresses=self.sort_addresses)

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

    def test_attr_same_value(self):
        with self.ip.interfaces[self.ifd] as testif:
            testif.set_mtu(testif.mtu)

    def test_idx_len(self):
        assert len(self.ip.by_name.keys()) == len(self.ip.by_index.keys())

    def test_idx_set(self):
        assert set(self.ip.by_name.values()) == set(self.ip.by_index.values())

    def test_idx_types(self):
        assert all(isinstance(i, int) for i in self.ip.by_index.keys())
        assert all(isinstance(i, basestring) for i in self.ip.by_name.keys())

    def test_norm_addr_ipv6(self):
        require_user('root')
        with self.ip.interfaces[self.ifd] as testif:
            testif.add_ip('0100:0100::1/64')
            testif.up()
        assert ('100:100::1', 64) in self.ip.interfaces[self.ifd].ipaddr

    def test_addr_mask_ipv6(self):
        require_user('root')
        with self.ip.interfaces[self.ifd] as testif:
            testif.add_ip('100:100::1', 'ffff:ffff:ffff:ffff::')
            testif.up()
        assert ('100:100::1', 64) in self.ip.interfaces[self.ifd].ipaddr

    def test_norm_route_ipv6(self):
        require_user('root')
        with self.ip.interfaces[self.ifd] as testif:
            testif.add_ip('0100:0100::1/64')
            testif.up()
        (self.ip.routes
         .add(dst='0200:0200::/64', gateway='0100:0100::2')
         .commit())

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
        assert self.ip.interfaces[if1].ipaddr[0]['flags'] is not None
        assert addr.get_attr('IFA_BROADCAST') is None

        index = self.ip.interfaces[if2]['index']
        addr = self.ip.nl.get_addr(index=index)[0]
        assert addr['scope'] == 0
        assert self.ip.interfaces[if2].ipaddr[0]['flags'] is not None
        assert addr.get_attr('IFA_BROADCAST') == '172.16.103.128'

    def test_addr_loaded(self):
        for name in self.ip.by_name:
            assert len(self.ip.interfaces[name]['ipaddr']) == \
                len(get_ip_addr(name))

    def test_addr_ordering(self):
        require_user('root')

        if1 = self.get_ifname()

        primaries = list()
        secondaries = list()
        with self.ip.create(ifname=if1, kind='dummy') as i:
            for o3 in reversed(range(1, 6)):
                for o4 in range(1, 4):
                    for mask in [24, 25]:
                        addr = '172.16.%d.%d/%d' % (o3, o4, mask)
                        i.add_ip(addr)
                        if o4 == 1:
                            primaries.append(addr)
                        else:
                            secondaries.append(addr)
        truth = primaries + secondaries

        self.ip.ipaddr.reload()
        addresses = list('%s/%d' % a for a in self.ip.interfaces[if1].ipaddr)

        assert truth == addresses

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

    def _vlan_flags(self, flags, result):
        require_user('root')

        ifA = self.get_ifname()
        ifV = self.get_ifname()
        self.ip.create(ifname=ifA, kind='dummy').commit()
        self.ip.create(ifname=ifV,
                       kind='vlan',
                       link=self.ip.interfaces[ifA],
                       vlan_id=101,
                       vlan_flags=flags).commit()
        assert ifV in self.ip.interfaces
        assert self.ip.interfaces[ifV].vlan_flags & result == result

    def test_vlan_flags_int(self):
        self._vlan_flags(2, 2)

    def test_vlan_flags_str(self):
        self._vlan_flags('gvrp', 2)

    def test_vlan_flags_dict(self):
        self._vlan_flags({'flags': 2, 'mask': 2}, 2)

    def test_vlan_flags_tuple_int(self):
        self._vlan_flags((2, 2), 2)

    def test_vlan_flags_tuple_str(self):
        self._vlan_flags(('gvrp', 'mvrp'), 10)

    def test_vlan_flags_list_int(self):
        self._vlan_flags([2, 2], 2)

    def test_vlan_flags_list_str(self):
        self._vlan_flags(['gvrp', 'mvrp'], 10)

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
        try:
            self.ip.interfaces.lo.review()
            raise Exception('you shall not pass')
        except TypeError:
            pass
        assert len(self.ip.interfaces.lo.local_tx) == 0
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
        try:
            self.ip.interfaces.lo.review()
            raise Exception('you shall not pass')
        except TypeError:
            pass

    def test_global_review_interface(self):
        try:
            self.ip.review()
            raise Exception('you shall not pass')
        except TypeError:
            pass

        if self.ip.mode == 'explicit':
            self.ip.interfaces.lo.begin()
        self.ip.interfaces.lo.add_ip('172.16.21.1/24')

        r = self.ip.review()
        assert len(r['interfaces']['lo']['+ipaddr']) == 1

        self.ip.drop()

        try:
            self.ip.review()
            raise Exception('you shall not pass')
        except TypeError:
            pass

    def test_global_review_route(self):
        try:
            self.ip.review()
            raise Exception('you shall not pass')
        except TypeError:
            pass

        self.ip.routes.add(table=2, dst='10.0.0.0/24', gateway='1.1.1.1')

        r = self.ip.review()
        assert len(r['routes'][2]) == 1
        assert r['routes'][2]['10.0.0.0/24']['gateway'] == '1.1.1.1'

        self.ip.drop()

        try:
            self.ip.review()
            raise Exception('you shall not pass')
        except TypeError:
            pass

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

    def _test_rules_action(self, spec, check):
        require_user('root')

        self.ip.rules.add(spec).commit()

        rules = self.ip.nl.get_rules(priority=spec['priority'])
        assert len(rules) == 1
        for field in check['fields']:
            assert rules[0][field] == check['fields'][field]
        for nla in check['nla']:
            assert rules[0].get_attr(nla) == check['nla'][nla]

        with self.ip.rules[spec['priority']] as r:
            r.remove()
        rules = self.ip.nl.get_rules(priority=spec['priority'])
        assert len(rules) == 0

    def test_rules_random_actions(self):
        random.seed(time.time())
        for _ in range(20):
            # bake check
            spec = {}
            check = {'fields': {}, 'nla': {}}
            # 1. priority
            spec['priority'] = check['nla']['FRA_PRIORITY'] = \
                random.randint(200, 2000)
            # 2. action
            spec['action'] = check['fields']['action'] = \
                random.randint(1, 8)
            if spec['action'] == 1:  # to_tbl
                spec['table'] = check['nla']['FRA_TABLE'] = \
                    random.randint(2, 20000)
            elif spec['action'] == 2:  # goto
                spec['goto'] = check['nla']['FRA_GOTO'] = \
                    random.randint(spec['priority'] + 1, 32767)
            # 3. src
            if random.random() > 0.5:
                src = '10.%i.0.0' % random.randint(0, 254)
                src_len = random.randint(16, 30)
                spec['src'] = src + '/' + str(src_len)
                check['fields']['src_len'] = src_len
                check['nla']['FRA_SRC'] = src
            # 4. dst
            if random.random() > 0.5:
                dst = '10.%i.0.0' % random.randint(0, 254)
                dst_len = random.randint(16, 30)
                spec['dst'] = dst + '/' + str(dst_len)
                check['fields']['dst_len'] = dst_len
                check['nla']['FRA_DST'] = dst

            # only if at least one of (dst, src) is specified
            if spec.get('dst', None) or spec.get('src', None):
                self._test_rules_action(spec, check)

    @skip_if_not_supported
    def test_routes_mpls_via_change(self):
        require_kernel(4, 4)
        require_user('root')
        idx = self.ip.interfaces[self.ifd]['index']
        label = 20

        self.ip.routes.add({'family': AF_MPLS,
                            'dst': label,
                            'newdst': [30],
                            'oif': idx}).commit()
        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_VIA') is None
        # 8<--------------
        with self.ip.routes.tables['mpls'][label] as r:
            r.via = {'family': socket.AF_INET,
                     'addr': '176.16.70.70'}
        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_VIA')['family'] == socket.AF_INET
        assert r.get_attr('RTA_VIA')['addr'] == '176.16.70.70'
        # 8<--------------
        with self.ip.routes.tables['mpls'][label] as r:
            r.via = {'family': socket.AF_INET,
                     'addr': '176.16.0.80'}
        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_VIA')['family'] == socket.AF_INET
        assert r.get_attr('RTA_VIA')['addr'] == '176.16.0.80'
        # 8<--------------
        with self.ip.routes.tables['mpls'][label] as r:
            r.via = {}
        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_VIA') is None
        # 8<--------------
        with self.ip.routes.tables['mpls'][label] as r:
            r.remove()
        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 0

    @skip_if_not_supported
    def test_routes_mpls_via_ipv4(self):
        require_kernel(4, 4)
        require_user('root')
        idx = self.ip.interfaces[self.ifd]['index']
        label = 20

        self.ip.routes.add({'family': AF_MPLS,
                            'dst': label,
                            'newdst': [30],
                            'via': {'family': socket.AF_INET,
                                    'addr': '176.16.70.70'},
                            'oif': idx}).commit()

        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_VIA')['family'] == socket.AF_INET
        assert r.get_attr('RTA_VIA')['addr'] == '176.16.70.70'

        with self.ip.routes.tables['mpls'][label] as r:
            r.remove()

        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 0

    @skip_if_not_supported
    def _test_routes_mpls_ops(self, label_in, labels_out=None):
        require_kernel(4, 4)
        require_user('root')
        idx = self.ip.interfaces[self.ifd]['index']

        self.ip.routes.add({'family': AF_MPLS,
                            'dst': label_in,
                            'newdst': labels_out,
                            'oif': idx}).commit()
        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_DST')[0]['label'] == label_in
        if labels_out:
            assert len(r.get_attr('RTA_NEWDST')) == len(labels_out)
            assert [x['label'] for x in r.get_attr('RTA_NEWDST')] == labels_out
        else:
            assert r.get_attr('RTA_NEWDST') is None
        with self.ip.routes.tables['mpls'][label_in] as r:
            r.remove()

    def test_routes_mpls_push(self):
        self._test_routes_mpls_ops(50, [50, 60])

    def test_routes_mpls_pop(self):
        self._test_routes_mpls_ops(50, None)

    def test_routes_mpls_swap(self):
        self._test_routes_mpls_ops(50, [60])

    @skip_if_not_supported
    def test_routes_multipath_transition_mpls(self):
        require_kernel(4, 4)
        require_user('root')

        self.ip.routes.add({'family': AF_MPLS,
                            'dst': 20,
                            'via': {'family': socket.AF_INET,
                                    'addr': '127.0.0.2'},
                            'oif': 1,
                            'newdst': [50]}).commit()

        routes = tuple(
            filter(lambda x: x.get_attr('RTA_DST')[0]['label'] == 20,
                   self.ip.nl.get_routes(family=AF_MPLS)))
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_OIF') == 1
        assert r.get_attr('RTA_NEWDST')[0]['label'] == 50
        assert r.get_attr('RTA_VIA')

        with self.ip.routes.tables['mpls'][20] as r:
            r.add_nh({'via': {'family': socket.AF_INET, 'addr': '127.0.0.3'},
                      'oif': 1,
                      'newdst': [60]})

        routes = tuple(
            filter(lambda x: x.get_attr('RTA_DST')[0]['label'] == 20,
                   self.ip.nl.get_routes(family=AF_MPLS)))
        assert len(routes) == 1
        r = routes[0]
        assert not r.get_attr('RTA_NEWDST')
        assert not r.get_attr('RTA_VIA')
        mp = r.get_attr('RTA_MULTIPATH')
        assert len(mp) == 2
        labels = [50, 60]
        for r in mp:
            labels.remove(r.get_attr('RTA_NEWDST')[0]['label'])
        assert len(labels) == 0

        with self.ip.routes.tables['mpls'][20] as r:
            r.del_nh({'via': {'family': socket.AF_INET, 'addr': '127.0.0.2'},
                      'oif': 1,
                      'newdst': [50]})

        routes = tuple(
            filter(lambda x: x.get_attr('RTA_DST')[0]['label'] == 20,
                   self.ip.nl.get_routes(family=AF_MPLS)))
        assert len(routes) == 1
        r = routes[0]
        assert r.get_attr('RTA_OIF') == 1
        assert r.get_attr('RTA_NEWDST')[0]['label'] == 60
        assert r.get_attr('RTA_VIA')
        assert not r.get_attr('RTA_MULTIPATH')

        with self.ip.routes.tables['mpls'][20] as r:
            r.remove()

    @skip_if_not_supported
    def test_routes_mpls_multipath(self):
        require_kernel(4, 4)
        require_user('root')

        req = {'family': AF_MPLS,
               'dst': 20,
               'multipath': [{'via': {'family': socket.AF_INET,
                                      'addr': '127.0.0.2'},
                              'oif': 1,
                              'newdst': [50]},
                             {'via': {'family': socket.AF_INET,
                                      'addr': '127.0.0.3'},
                              'oif': 1,
                              'newdst': [60, 70]}]}
        r = self.ip.routes.add(req)
        r.commit()
        routes = tuple(
            filter(lambda x: x.get_attr('RTA_DST')[0]['label'] == 20,
                   self.ip.nl.get_routes(family=AF_MPLS)))
        assert len(routes) == 1
        r = routes[0]
        assert r['family'] == AF_MPLS
        assert not r.get_attr('RTA_OIF')
        assert not r.get_attr('RTA_VIA')
        assert not r.get_attr('RTA_NEWDST')
        assert len(r.get_attr('RTA_MULTIPATH')) == 2
        for nh in r.get_attr('RTA_MULTIPATH'):
            try:
                assert nh.get('oif', None) == 1
                assert nh.get_attr('RTA_VIA')['addr'] == '127.0.0.2'
                assert len(nh.get_attr('RTA_NEWDST')) == 1
                assert nh.get_attr('RTA_NEWDST')[0]['label'] == 50
            except:
                assert nh.get('oif', None) == 1
                assert nh.get_attr('RTA_VIA')['addr'] == '127.0.0.3'
                assert len(nh.get_attr('RTA_NEWDST')) == 2
                assert nh.get_attr('RTA_NEWDST')[0]['label'] == 60
                assert nh.get_attr('RTA_NEWDST')[1]['label'] == 70
        with self.ip.routes.tables['mpls'][20] as r:
            r.del_nh({'via': {'addr': '127.0.0.2'},
                      'oif': 1,
                      'newdst': [50],
                      'family': AF_MPLS})
            r.add_nh({'via': {'addr': '127.0.0.4',
                              'family': socket.AF_INET},
                      'oif': 1,
                      'newdst': [80, 90],
                      'family': AF_MPLS})

        assert len(r['multipath']) == 2
        routes = tuple(
            filter(lambda x: x.get_attr('RTA_DST')[0]['label'] == 20,
                   self.ip.nl.get_routes(family=AF_MPLS)))
        assert len(routes) == 1
        r = routes[0]
        assert r['family'] == AF_MPLS
        assert not r.get_attr('RTA_OIF')
        assert not r.get_attr('RTA_VIA')
        assert not r.get_attr('RTA_NEWDST')
        assert len(r.get_attr('RTA_MULTIPATH')) == 2
        for nh in r.get_attr('RTA_MULTIPATH'):
            try:
                assert nh.get('oif', None) == 1
                assert nh.get_attr('RTA_VIA')['addr'] == '127.0.0.4'
                assert len(nh.get_attr('RTA_NEWDST')) == 2
                assert nh.get_attr('RTA_NEWDST')[0]['label'] == 80
                assert nh.get_attr('RTA_NEWDST')[1]['label'] == 90
            except:
                assert nh.get('oif', None) == 1
                assert nh.get_attr('RTA_VIA')['addr'] == '127.0.0.3'
                assert len(nh.get_attr('RTA_NEWDST')) == 2
                assert nh.get_attr('RTA_NEWDST')[0]['label'] == 60
                assert nh.get_attr('RTA_NEWDST')[1]['label'] == 70
        with self.ip.routes.tables['mpls'][20] as r:
            r.remove()

    @skip_if_not_supported
    def test_routes_mpls(self):
        require_kernel(4, 4)
        require_user('root')
        idx = self.ip.interfaces[self.ifd]['index']
        label = 20

        self.ip.routes.add({'family': AF_MPLS,
                            'dst': label,
                            'newdst': [30],
                            'oif': idx}).commit()

        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert r['family'] == AF_MPLS
        assert len(r.get_attr('RTA_DST')) == 1
        assert r.get_attr('RTA_DST')[0]['label'] == label
        assert len(r.get_attr('RTA_NEWDST')) == 1
        assert r.get_attr('RTA_NEWDST')[0]['label'] == 30
        assert r.get_attr('RTA_OIF') == idx
        assert r.get_attr('RTA_VIA') is None

        with self.ip.routes.tables['mpls'][label] as r:
            r['newdst'] = [40, 50]

        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 1
        r = routes[0]
        assert len(r.get_attr('RTA_DST')) == 1
        assert r.get_attr('RTA_DST')[0]['label'] == label
        assert len(r.get_attr('RTA_NEWDST')) == 2
        assert r.get_attr('RTA_NEWDST')[0]['label'] == 40
        assert r.get_attr('RTA_NEWDST')[0]['bos'] == 0
        assert r.get_attr('RTA_NEWDST')[1]['label'] == 50
        assert r.get_attr('RTA_NEWDST')[1]['bos'] == 1

        with self.ip.routes.tables['mpls'][label] as r:
            r.remove()

        routes = self.ip.nl.get_routes(family=AF_MPLS, oif=idx)
        assert len(routes) == 0

    @skip_if_not_supported
    def test_routes_lwtunnel_mpls_multipath(self):
        require_kernel(4, 4)
        require_user('root')

        # ordinary route
        req = {'table': 1002,
               'dst': '12.11.11.1/32',
               'oif': 1,
               'gateway': '127.0.0.1',
               # labels as a list of dicts
               'encap': {'labels': [{'bos': 1, 'label': 192}],
                         'type': AF_MPLS}}
        r = self.ip.routes.add(req).commit()
        routes = self.ip.nl.get_routes(table=1002)
        assert len(routes) == 1
        assert (routes[0]
                .get_attr('RTA_ENCAP')
                .get_attr('MPLS_IPTUNNEL_DST')[0]['label']) == 192
        with r:
            r.remove()

        # multipath with one target
        #
        # the request is valid, but on the OS level it
        # results in an ordinary non-multipath route
        #
        # IPDB should deal with it
        req = {'table': 1003,
               'dst': '12.11.11.2/32',
               'multipath': [{'oif': 1,
                              'gateway': '127.0.0.1',
                              # labels as a list of ints
                              'encap': {'labels': [193],
                                        'type': 'mpls'}}]}
        r = self.ip.routes.add(req).commit()
        routes = self.ip.nl.get_routes(table=1003)
        assert len(routes) == 1
        assert (routes[0]
                .get_attr('RTA_ENCAP')
                .get_attr('MPLS_IPTUNNEL_DST')[0]['label']) == 193
        with r:
            r.remove()

        # multipath route with two targets
        req = {'table': 1004,
               'dst': '12.11.11.3/32',
               'multipath': [{'oif': 1,
                              'gateway': '127.0.0.1',
                              # labels as a list of ints
                              'encap': {'labels': [192, 200],
                                        'type': AF_MPLS}},
                             {'oif': 1,
                              'gateway': '127.0.0.1',
                              # labels as a string
                              'encap': {'labels': "177/300",
                                        'type': 'mpls'}}]}
        self.ip.routes.add(req).commit()
        routes = self.ip.nl.get_routes(table=1004)
        assert len(routes) == 1
        for i in range(2):
            l1 = (routes[0]
                  .get_attr('RTA_MULTIPATH')[i]
                  .get_attr('RTA_ENCAP')
                  .get_attr('MPLS_IPTUNNEL_DST')[0]['label'])
            l2 = (routes[0]
                  .get_attr('RTA_MULTIPATH')[i]
                  .get_attr('RTA_ENCAP')
                  .get_attr('MPLS_IPTUNNEL_DST')[1]['label'])
            try:
                assert l1 == 192
                assert l2 == 200
            except:
                assert l1 == 177
                assert l2 == 300

        with self.ip.routes.tables[1004]['12.11.11.3/32'] as r:
            r.del_nh({'oif': 1,
                      'gateway': '127.0.0.1',
                      # labels as a list of dicts
                      'encap': {'labels': [{'bos': 0, 'label': 192},
                                           {'bos': 1, 'label': 200}],
                                # type as int
                                'type': 1}})
            r.add_nh({'oif': 1,
                      'gateway': '127.0.0.1',
                      # type as string
                      'encap': {'labels': '192/660', 'type': 'mpls'}})
        routes = self.ip.nl.get_routes(table=1004)
        assert len(routes) == 1
        for i in range(2):
            l1 = (routes[0]
                  .get_attr('RTA_MULTIPATH')[i]
                  .get_attr('RTA_ENCAP')
                  .get_attr('MPLS_IPTUNNEL_DST')[0]['label'])
            l2 = (routes[0]
                  .get_attr('RTA_MULTIPATH')[i]
                  .get_attr('RTA_ENCAP')
                  .get_attr('MPLS_IPTUNNEL_DST')[1]['label'])
            try:
                assert l1 == 192
                assert l2 == 660
            except:
                assert l1 == 177
                assert l2 == 300
        with self.ip.routes.tables[1004]['12.11.11.3/32'] as r:
            r.remove()

    @skip_if_not_supported
    def test_routes_lwtunnel_mpls_metrics(self):
        require_kernel(4, 4)
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
    def test_routes_lwtunnel_mpls(self):
        require_kernel(4, 4)
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
    def test_routes_lwtunnel_mpls_change(self):
        require_kernel(4, 4)
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

    def test_default_route_notation(self):
        require_user('root')

        (self.ip.routes
         .add(dst='0.0.0.0/0', gateway='127.0.0.6', table=180)
         .commit())

        assert self.ip.routes.tables[180]['default']['gateway'] == '127.0.0.6'
        assert grep('ip ro show table 180',
                    pattern='default.*127.0.0.6')
        with self.ip.routes.tables[180]['default'] as r:
            r.remove()

    def test_routes_mixed_ipv4_ipv6(self):
        require_user('root')

        with self.ip.interfaces[self.ifd] as testif:
            testif.add_ip('2001:4c8:1023:108::39/64')
            testif.add_ip('172.19.0.2/24')
            testif.up()

        (self.ip.routes
         .add({'dst': 'default',
               'table': 100,
               'gateway': '2001:4c8:1023:108::40'})
         .commit())
        (self.ip.routes
         .add({'dst': 'default',
               'table': 100,
               'gateway': '172.19.0.1'})
         .commit())

        assert grep('ip -6 ro show table 100',
                    pattern='default.*2001:4c8:1023:108::40')
        assert grep('ip ro show table 100',
                    pattern='default.*172.19.0.1')

        r4 = self.ip.routes.tables[100][{'dst': 'default',
                                         'family': socket.AF_INET}]
        r6 = self.ip.routes.tables[100][{'dst': 'default',
                                         'family': socket.AF_INET6}]

        assert r4.gateway == '172.19.0.1'
        assert r6.gateway == '2001:4c8:1023:108::40'

        if self.ip.mode == 'explicit':
            r4.begin()
            r6.begin()
        r4.remove().commit()
        r6.remove().commit()

        assert not grep('ip -6 ro show table 100',
                        pattern='default.*2001:4c8:1023:108::40')
        assert not grep('ip ro show table 100',
                        pattern='default.*172.19.0.1')

    def test_routes_ipv6(self):
        require_user('root')
        i = self.ip.create(ifname=uifname(), kind='dummy')
        with i:
            i.add_ip('2001:4c8:1023:108::39/64')
            i.up()
        r = self.ip.routes.add({'dst': 'fd00:6d:3d1a::/64',
                                'gateway': '2001:4c8:1023:108::40'})
        r.commit()
        assert grep('ip -6 ro', pattern='fd00:6d:3d1a::')
        assert 'fd00:6d:3d1a::/64' in self.ip.routes.keys()

        if self.ip.mode == 'explicit':
            r.begin()
        r.remove().commit()
        assert not grep('ip -6 ro', pattern='fd00:6d:3d1a::')
        assert 'fd00:6d:3d1a::/64' not in self.ip.routes.keys()

        if self.ip.mode == 'explicit':
            i.begin()
        i.remove().commit()

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

    def test_routes_del_nh_fail(self):
        require_user('root')
        with self.ip.routes.add({'dst': '172.16.0.0/24',
                                 'gateway': '127.0.0.2'}):
            pass
        try:
            with self.ip.routes['172.16.0.0/24'] as r:
                r.del_nh({'gateway': '127.0.0.2'})
        except KeyError:
            pass
        finally:
            with self.ip.routes['172.16.0.0/24'] as r:
                r.remove()

    def test_routes_set_priority(self):
        require_user('root')
        assert '172.16.0.0/24' not in self.ip.routes
        with self.ip.routes.add({'dst': '172.16.0.0/24',
                                 'gateway': '127.0.0.2',
                                 'priority': 100}) as r:
            pass
        assert '172.16.0.0/24' in self.ip.routes.keys()
        assert grep('ip ro', pattern='172.16.0.0/24.*127.0.0.2.*100')
        # change the priority
        with self.ip.routes['172.16.0.0/24'] as r:
            r.priority = 287
        # check the changes
        assert len(grep('ip ro', pattern='172.16.0.0/24.*127.0.0.2')) == 1
        assert grep('ip ro', pattern='172.16.0.0/24.*127.0.0.2.*287')
        assert self.ip.routes['172.16.0.0/24'].priority == 287
        # delete the route
        with self.ip.routes['172.16.0.0/24'] as r:
            r.remove()

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

    def test_routes_multipath_transition(self):
        require_user('root')
        ifR = self.get_ifname()

        with self.ip.create(ifname=ifR, kind='dummy') as i:
            i.add_ip('172.16.229.2/24')
            i.up()

        (self.ip
         .routes
         .add({'dst': '172.16.228.0/24', 'gateway': '172.16.229.3'})
         .commit())

        r = self.ip.nl.get_routes(match={'dst': '172.16.228.0'})
        assert len(r) == 1
        assert r[0].get_attr('RTA_GATEWAY') == '172.16.229.3'
        assert self.ip.routes['172.16.228.0/24']['gateway'] == '172.16.229.3'

        with self.ip.routes['172.16.228.0/24'] as i:
            i.add_nh({'gateway': '172.16.229.4'})
            i.add_nh({'gateway': '172.16.229.5'})

        gws = set(('172.16.229.3', '172.16.229.4', '172.16.229.5'))
        iws = set([x['gateway'] for x in
                   self.ip.routes['172.16.228.0/24']['multipath']])
        rws = set([x.get_attr('RTA_GATEWAY') for x in
                   (self.ip.nl
                    .get_routes(match={'dst': '172.16.228.0'})[0]
                    .get_attr('RTA_MULTIPATH'))])
        assert gws == rws == iws

        with self.ip.routes['172.16.228.0/24'] as i:
            i.del_nh({'gateway': '172.16.229.3'})
            i.del_nh({'gateway': '172.16.229.5'})

        r = self.ip.nl.get_routes(match={'dst': '172.16.228.0'})
        assert len(r) == 1
        assert r[0].get_attr('RTA_GATEWAY') == '172.16.229.4'
        assert self.ip.routes['172.16.228.0/24']['gateway'] == '172.16.229.4'

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
        assert not grep('ip ro', pattern='nexthop.*172.16.231.2.*weight.*21')

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

    def test_wait_ipv6(self):
        ifa = self.get_ifname()
        with self.ip.create(ifname=ifa, kind='dummy') as i:
            # add IPv6 addr
            i.up()
            i.add_ip('2001:21:21:21::/64')
        ts1 = time.time()
        a = self.ip.interfaces[ifa].wait_ip('2001:21:21:21::',
                                            mask=64,
                                            timeout=2)
        b = self.ip.interfaces[ifa].wait_ip('2001:22:22:22::',
                                            mask=64,
                                            timeout=2)
        ts2 = time.time()
        assert (ts2 - ts1) > 2
        assert (ts2 - ts1) < 4
        assert a is True
        assert b is False

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
            i.drop()
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
                interface.ipaddr.target.wait(3)
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
        # double freeze: subsequent freezes should raise RuntimeError()
        try:
            interface.freeze()
        except RuntimeError:
            pass

        # change the interface somehow
        i2 = IPRoute()
        for addr in ('172.16.0.1', '172.16.1.1'):
            for _ in range(5):
                try:
                    i2.addr('delete', interface.index, addr, 24)
                    break
                except:
                    pass
                time.sleep(0.5)
        probe()

        # unfreeze
        self.ip.interfaces[self.ifd].unfreeze()

        for addr in ('172.16.0.1', '172.16.1.1'):
            for _ in range(5):
                try:
                    i2.addr('delete', interface.index, addr, 24)
                    break
                except:
                    pass
                time.sleep(0.5)
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

    def test_ipaddr_views(self):
        require_user('root')

        ifA = self.get_ifname()
        i = (self.ip
             .create(kind='dummy', ifname=ifA)
             .add_ip('172.16.0.1/24')
             .add_ip('fdb3:84e5:4ff4:55e4::1/64')
             .commit())

        assert len(i.ipaddr.ipv4) + len(i.ipaddr.ipv6) == len(i.ipaddr)
        assert len(i.ipaddr) >= 2

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

    def test_bridge_port_options(self):
        require_user('root')
        ifA = self.get_ifname()
        ifB = self.get_ifname()

        self.ip.create(ifname=ifA,
                       kind='dummy').commit()
        self.ip.create(ifname=ifB,
                       kind='bridge').commit()

        with self.ip.interfaces[ifB] as i:
            i.add_port(ifA)
            i.up()

        with self.ip.interfaces[ifA] as i:
            i.up()
            i.brport_unicast_flood = 0
            i.brport_cost = 500

        assert self.ip.interfaces[ifA]['brport_unicast_flood'] == 0
        assert self.ip.interfaces[ifA]['brport_cost'] == 500
        assert self.ip.interfaces[ifA]['master'] == \
            self.ip.interfaces[ifB]['index']

    def test_bridge_controls_set(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        self.ip.create(ifname=ifA,
                       kind='dummy').commit()
        self.ip.create(ifname=ifB,
                       kind='bridge').commit()

        with self.ip.interfaces[ifB] as i:
            i.add_port(ifA)
            i.up()
            i['br_stp_state'] = 0
            i['br_forward_delay'] = 500

        assert self.ip.interfaces[ifB]['br_stp_state'] == 0
        assert self.ip.interfaces[ifB]['br_forward_delay'] == 500
        assert self.ip.interfaces[ifA]['master'] == \
            self.ip.interfaces[ifB]['index']

    def test_bridge_controls_add(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        self.ip.create(ifname=ifA,
                       kind='dummy').commit()
        with self.ip.create(ifname=ifB, kind='bridge') as i:
            i.add_port(ifA)
            i.up()
            i.set_br_stp_state(0)
            i.set_br_forward_delay(500)

        assert self.ip.interfaces[ifB]['br_stp_state'] == 0
        assert self.ip.interfaces[ifB]['br_forward_delay'] == 500
        assert self.ip.interfaces[ifA]['master'] == \
            self.ip.interfaces[ifB]['index']

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

    def test_global_deps(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        # Set up the environment:
        # 1. interface 172.16.178.2/24
        # 2. route 172.16.179.0/24 via 172.16.178.1

        with self.ip.interfaces.add(ifname=ifA, kind='dummy') as i:
            i.up()
            i.set_address('00:11:22:33:44:55')
            i.set_mtu(1280)
            i.add_ip('172.16.178.2/24')

        (self.ip.routes
         .add(dst='172.16.179.0/24', gateway='172.16.178.1')
         .commit())

        # Now prepare the transaction that will fail
        if self.ip.mode == 'explicit':
            self.ip.interfaces[ifA].begin()

        (self.ip.interfaces[ifA]
         .set_ipdb_priority(20)  # <-- executed first
         .remove())  # <-- causes the route to be dropped from the system

        (self.ip.interfaces
         .add(ifname=ifB, kind='dummy')
         .up()
         .set_ipdb_priority(10)  # <-- executed second
         .set_address('11:22:33:44:55:66'))  # <--- error

        try:
            self.ip.commit()
        except NetlinkError:
            pass

        # Expected result:
        #
        # ifA (re-created):
        #   - is up
        #   - ip address is back
        #   - mtu 1280
        #   - mac address is 00:11:22:33:44:55
        # ifB:
        #   - not created
        #   - in the 'create' state
        # the route:
        #   - exists (re-created)
        #
        # Since the ifA interface was completely removed, we should
        # ensure that the interface created from the scratch has
        # the same mac address, the same index and other attributes.
        #
        # Pls keep in mind, that old kernels do not allow setting up
        # the interface index, so this functionality will not be
        # available.
        #
        # FIXME: check which the kernel version is required.

        assert ifA in self.ip.interfaces
        assert self.ip.interfaces[ifA]['flags'] & 1
        assert ('172.16.178.2', 24) in self.ip.interfaces[ifA]['ipaddr']
        assert self.ip.interfaces[ifA]['mtu'] == 1280
        assert self.ip.interfaces[ifA]['address'] == '00:11:22:33:44:55'
        assert ifB in self.ip.interfaces
        assert self.ip.interfaces[ifB]['ipdb_scope'] == 'create'
        assert '172.16.179.0/24' in self.ip.routes
        assert self.ip.routes['172.16.179.0/24']['ipdb_scope'] == 'system'

        assert grep('ip ro', pattern='172.16.179.0/24')
        assert grep('ip ad', pattern='172.16.178.2/24')

    def test_global_rollback(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()

        # create interface and route
        with self.ip.interfaces.add(ifname=ifA, kind='dummy') as i:
            i.up()
            i.add_ip('172.16.182.2/24')

        (self.ip.routes
         .add(dst='172.16.183.0/24', gateway='172.16.182.1')
         .commit())

        # now try a transaction:
        # 1. remove the interface
        # 2. create another inteface  <--- here comes an exception
        # 3. create another route

        if self.ip.mode == 'explicit':
            self.ip.interfaces[ifA].begin()

        self.ip.interfaces[ifA].remove()
        self.ip.routes.add(dst='172.16.185.0/24', gateway='172.16.184.1')
        (self.ip
         .create(ifname=ifB, kind='dummy')
         .set_mtu(1500)
         .set_address('11:22:33:44:55:66')
         .add_ip('172.16.184.2/24'))

        # commit global transaction
        try:
            self.ip.commit()
        except NetlinkError:
            pass

        # expected results:
        # 1. interface ifA exists and has the same parameters
        # 2. the route via 172.16.182.1 exists
        # 3. interface ifB exists only in the DB, not on the system
        # 4. the route via 172.16.184.1 doesn't exist

        assert ifA in self.ip.interfaces
        assert ifB in self.ip.interfaces
        assert self.ip.interfaces[ifB].ipdb_scope == 'create'
        assert grep('ip link', pattern=ifA)
        assert not grep('ip link', pattern=ifB)

    def test_global_mixed(self):
        require_user('root')

        ifA = self.get_ifname()
        ifB = self.get_ifname()
        ifC = self.get_ifname()

        self.ip.routes.add({'dst': '172.18.1.0/24',
                            'gateway': '127.0.0.1'})
        self.ip.routes.add({'dst': '172.18.2.0/24',
                            'gateway': '127.0.0.1'})
        self.ip.interfaces.add(ifname=ifA, kind='dummy')
        self.ip.interfaces.add(ifname=ifB, kind='dummy')

        self.ip.interfaces.add(ifname=ifA + 'v100',
                               kind='vlan',
                               vlan_id=100,
                               link=self.ip.interfaces[ifA])
        self.ip.interfaces.add(ifname=ifB + 'v200',
                               kind='vlan',
                               vlan_id=200,
                               link=self.ip.interfaces[ifB])
        self.ip.interfaces.add(ifname=ifC, kind='bridge')
        self.ip.interfaces[ifC].add_port(ifA + 'v100')
        self.ip.interfaces[ifC].add_port(ifB + 'v200')

        self.ip.commit()
        assert grep('ip ro', pattern='172.18.1.0/24.*127.0.0.1')
        assert grep('ip ro', pattern='172.18.2.0/24.*127.0.0.1')

        if self.ip.mode == 'explicit':
            self.ip.routes['172.18.1.0/24'].begin()
            self.ip.routes['172.18.2.0/24'].begin()
        self.ip.routes['172.18.1.0/24'].remove()
        self.ip.routes['172.18.2.0/24'].remove()

        self.ip.commit()
        assert not grep('ip ro', pattern='172.18.1.0/24.*127.0.0.1')
        assert not grep('ip ro', pattern='172.18.2.0/24.*127.0.0.1')

    def test_global_routes_fail(self):

        self.ip.routes.add(dst='172.18.0.0/24',
                           gateway='1.1.1.1',
                           table=100)

        try:
            self.ip.commit()
        except NetlinkError:
            pass

        assert '172.18.0.0/24' in self.ip.routes.tables[100]
        assert (self.ip
                .routes
                .tables[100]['172.18.0.0/24']['ipdb_scope'] == 'create')

        with self.ip.routes.tables[100]['172.18.0.0/24'] as r:
            r['gateway'] = '127.0.0.2'
        assert '172.18.0.0/24' in self.ip.routes.tables[100]
        assert grep('ip ro show table 100', pattern='172.18.0.0/24')

        with self.ip.routes.tables[100]['172.18.0.0/24'] as r:
            r.remove()
        assert '172.18.0.0/24' not in self.ip.routes.tables[100]
        assert not grep('ip ro show table 100', pattern='172.18.0.0/24')

    def test_global_routes(self):
        require_user('root')

        self.ip.routes.add({'dst': '172.18.1.0/24',
                            'gateway': '127.0.0.1'})
        self.ip.routes.add({'dst': '172.18.2.0/24',
                            'gateway': '127.0.0.1'})

        self.ip.commit()
        assert grep('ip ro', pattern='172.18.1.0/24.*127.0.0.1')
        assert grep('ip ro', pattern='172.18.2.0/24.*127.0.0.1')

        if self.ip.mode == 'explicit':
            self.ip.routes['172.18.1.0/24'].begin()
            self.ip.routes['172.18.2.0/24'].begin()
        self.ip.routes['172.18.1.0/24'].remove()
        self.ip.routes['172.18.2.0/24'].remove()

        self.ip.commit()
        assert not grep('ip ro', pattern='172.18.1.0/24.*127.0.0.1')
        assert not grep('ip ro', pattern='172.18.2.0/24.*127.0.0.1')

    # @skip_if_not_supported
    def test_bridge_vlans_self(self):
        require_user('root')
        ifB = self.get_ifname()
        ifP1 = self.get_ifname()
        ifP2 = self.get_ifname()

        br = (self.ip
              .interfaces
              .add(ifname=ifB, kind='bridge')
              .commit())
        p1 = (self.ip
              .interfaces
              .add(ifname=ifP1, kind='dummy')
              .commit())
        p2 = (self.ip
              .interfaces
              .add(ifname=ifP2, kind='dummy')
              .commit())

        assert len(p1.vlans) == 0
        assert len(p2.vlans) == 0

        with br:
            br.add_port(p1)
            br.add_port(p2)

        with p1:
            p1.add_vlan(302)
            p1.add_vlan(304)

        with p2:
            p2.add_vlan(303)
            p2.add_vlan(305)

        with br:
            br.add_vlan(302, 'self')
            br.add_vlan(303, 'self')
            br.add_vlan(304, 'self')
            br.add_vlan(305, 'self')

        assert p1.vlans == set((1, 302, 304))
        assert p2.vlans == set((1, 303, 305))
        assert br.vlans == set((1, 302, 303, 304, 305))

    @skip_if_not_supported
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
        assert p.vlans[202][0]['flags'] == 6
        assert p.vlans[204][0]['flags'] == 0
        assert p.vlans[206][0]['flags'] == 0

    def test_bridge_vlans(self):
        require_user('root')
        ifB = self.get_ifname()
        ifP = self.get_ifname()
        b = self.ip.create(ifname=ifB, kind='bridge').commit()
        p = self.ip.create(ifname=ifP, kind='dummy').commit()
        assert len(p.vlans) == 0

        with b:
            b.add_port(p)

        # IPDB doesn't sync on implicit vlans, so we have to
        # wait here
        time.sleep(1)

        # skip if not supported
        if len(p.vlans) == 0:
            raise SkipTest('feature not supported by platform')

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

    def test_create_macaddr(self):
        #
        # https://github.com/svinota/pyroute2/issues/454
        #
        require_user('root')
        ifA = self.get_ifname()
        ifB = self.get_ifname()
        ifC = self.get_ifname()

        # lowercase
        (self.ip.interfaces
         .add(ifname=ifA, kind='dummy')
         .set_address('00:11:22:aa:bb:c0')
         .commit())

        # uppercase
        (self.ip.interfaces
         .add(ifname=ifB, kind='dummy')
         .set_address('00:11:22:AA:BB:C1')
         .commit())

        # one request, mix cases
        (self.ip.interfaces
         .add(ifname=ifC, kind='dummy', address='00:11:22:AA:bb:C2')
         .commit())

    def test_create_fail(self):
        ifname = uifname()
        kind = uifname()
        interface = self.ip.create(ifname=ifname, kind=kind)
        try:
            with self.ip.interfaces[ifname] as i:
                pass
        except:
            pass
        assert ifname in self.ip.interfaces
        assert self.ip.interfaces[ifname]['ipdb_scope'] == 'create'
        assert self.ip.interfaces[ifname]['kind'] == kind

        with self.ip.interfaces[ifname] as i:
            i.remove()

        assert ifname not in self.ip.interfaces
        assert interface['ipdb_scope'] == 'invalid'

    def test_create_fail_repeat1(self):
        require_user('root')

        ifA = self.get_ifname()
        try:
            (self
             .ip
             .create(kind='dummy', ifname=ifA, address='11:22:33:44:55:66')
             .commit())
        except NetlinkError:
            pass

        assert ifA in self.ip.interfaces
        assert self.ip.interfaces[ifA]['ipdb_scope'] == 'create'
        # mac IS specified in create()
        assert self.ip.interfaces[ifA]['address'] == '11:22:33:44:55:66'

        # reset the address to some valid, otherwise commit() will fail again
        self.ip.interfaces[ifA]['address'] = '00:11:22:33:44:55'
        self.ip.interfaces[ifA].commit()

        assert self.ip.interfaces[ifA]['ipdb_scope'] == 'system'
        assert self.ip.interfaces[ifA]['address'] is not None
        assert self.ip.interfaces[ifA]['index'] > 0

    def test_create_fail_repeat2(self):
        require_user('root')

        ifA = self.get_ifname()
        try:
            with self.ip.create(kind='dummy', ifname=ifA) as i:
                # invalid mac address
                i['address'] = '11:22:33:44:55:66'
        except NetlinkError:
            pass

        assert ifA in self.ip.interfaces
        assert self.ip.interfaces[ifA]['ipdb_scope'] == 'create'
        # mac NOT specified in create()
        assert self.ip.interfaces[ifA]['address'] != '11:22:33:44:55:66'

        # reset the address to some valid, otherwise commit() will fail again
        self.ip.interfaces[ifA]['address'] = '00:11:22:33:44:55'
        self.ip.interfaces[ifA].commit()

        assert self.ip.interfaces[ifA]['ipdb_scope'] == 'system'
        assert self.ip.interfaces[ifA]['address'] is not None
        assert self.ip.interfaces[ifA]['index'] > 0

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
    def test_create_ip6gre(self):
        require_user('root')

        ifL = self.get_ifname()
        ifV = self.get_ifname()
        with self.ip.create(kind='dummy', ifname=ifL) as i:
            i.add_ip('2001:dba::1/64')
            i.up()

        self.ip.create(kind='ip6gre',
                       ifname=ifV,
                       ip6gre_local='2001:dba::1',
                       ip6gre_remote='2001:dba::2',
                       ip6gre_ttl=16).commit()

        ip2 = IPDB()
        ifdb = ip2.interfaces
        try:
            assert ifdb[ifV].ip6gre_local == '2001:dba::1'
            assert ifdb[ifV].ip6gre_remote == '2001:dba::2'
            assert ifdb[ifV].ip6gre_ttl == 16
        except Exception:
            raise
        finally:
            ip2.release()

    @skip_if_not_supported
    def test_create_ip6gretap(self):
        require_user('root')

        ifL = self.get_ifname()
        ifV = self.get_ifname()
        with self.ip.create(kind='dummy', ifname=ifL) as i:
            i.add_ip('2001:dba::1/64')
            i.up()

        self.ip.create(kind='ip6gretap',
                       ifname=ifV,
                       ip6gre_local='2001:dba::1',
                       ip6gre_ikey=1,
                       ip6gre_okey=2,
                       ip6gre_iflags=0x0020,
                       ip6gre_oflags=0x0020,
                       ip6gre_ttl=16).commit()

        ip2 = IPDB()
        ifdb = ip2.interfaces
        try:
            assert ifdb[ifV].ip6gre_local == '2001:dba::1'
            assert ifdb[ifV].ip6gre_ikey == 1
            assert ifdb[ifV].ip6gre_okey == 2
            assert ifdb[ifV].ip6gre_iflags == 0x0020
            assert ifdb[ifV].ip6gre_oflags == 0x0020
            assert ifdb[ifV].ip6gre_ttl == 16
        except Exception:
            raise
        finally:
            ip2.release()

    @skip_if_not_supported
    def test_create_vrf(self):
        require_user('root')

        ifL = self.get_ifname()
        self.ip.create(kind='vrf',
                       ifname=ifL,
                       vrf_table=100,
                       reuse=True).commit()

        assert ifL in self.ip.interfaces
        assert self.ip.interfaces[ifL].vrf_table == 100
        assert self.ip.interfaces[ifL].kind == 'vrf'

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

    def test_create_vlan_8021ad(self):
        require_user('root')
        require_8021q()

        host = self.get_ifname()  # host interface
        stag = self.get_ifname()  # 802.1ad, 0x88a8, s-tag
        ctag = self.get_ifname()  # 802.1q, 0x8100, c-tag

        (self.ip.interfaces
         .add(ifname=host, kind='dummy')
         .up()
         .commit())

        (self.ip.interfaces
         .add(ifname=stag, kind='vlan', link=host,
              vlan_id=101, vlan_protocol=0x88a8)
         .up()
         .commit())

        (self.ip.interfaces
         .add(ifname=ctag, kind='vlan', link=stag,
              vlan_id=201, vlan_protocol=0x8100)
         .up()
         .commit())

        assert self.ip.interfaces[stag]['vlan_protocol'] == 0x88a8
        assert self.ip.interfaces[ctag]['vlan_protocol'] == 0x8100

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
        t = b.current_tx
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


class TestMisc(object):

    def setup(self):
        self.ifname = uifname()
        create_link(self.ifname, 'dummy')

    def teardown(self):
        remove_link(self.ifname)

    def test_eventqueue(self):
        require_user('root')
        # prepare the queue thread

        def t(ret):
            with IPDB() as ipdb:
                with ipdb.eventqueue() as evq:
                    for msg in evq:
                        if msg.get_attr('IFLA_IFNAME') == 'test1984':
                            ret.append(msg)
                            return
        ret = []
        th = threading.Thread(target=t, args=(ret, ))
        th.setDaemon(True)
        th.start()
        # generate the event
        with IPDB() as ipdb:
            ipdb.interfaces.add(ifname='test1984', kind='dummy').commit()

        # join the thread
        th.join(5)
        try:
            assert len(ret) == 1
        finally:
            with IPDB() as ipdb:
                ipdb.interfaces.test1984.remove().commit()

    def test_global_only_routes(self):
        require_user('root')
        try:
            with IPDB(plugins=['routes']) as ipdb:
                (ipdb.routes
                 .add(dst='172.18.0.0/24',
                      gateway='127.0.0.2',
                      table=100))

                ipdb.commit()

                assert grep('ip ro show table 100', pattern='172.18.0.0/24')
        finally:
            with IPDB() as ipdb:
                if '172.18.0.0/24' in ipdb.routes.tables.get(100, {}):
                    ipdb.routes.tables[100]['172.18.0.0/24'].remove().commit()

    def test_global_only_interfaces(self):
        require_user('root')
        ifA = uifname()
        try:
            with IPDB(plugins=['interfaces']) as ipdb:
                (ipdb.interfaces
                 .add(ifname=ifA, kind='dummy')
                 .add_ip('172.18.0.2/24')
                 .up())

                ipdb.commit()

                assert grep('ip link', pattern=ifA)
                assert grep('ip ad', pattern='172.18.0.2/24')
        finally:
            with IPDB() as ipdb:
                if ifA in ipdb.interfaces:
                    ipdb.interfaces[ifA].remove().commit()

    def test_global_wo_interfaces(self):
        pass

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
            assert 0 < (ts2 - ts1) < 2
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
            assert 5 < (ts2 - ts1) < 7
        except:
            raise
        finally:
            config.commit_barrier = 0.2
            ip.interfaces[ifname].remove().commit()
            ip.release()

    def test_read_only_cm(self):
        with IPDB() as ip:
            with ip.interfaces.lo.ro as i:
                assert i.current_tx is None

    def test_fail_released(self):
        ip = IPDB()
        assert len(ip.interfaces.keys()) > 0
        ip.release()
        assert len(ip.interfaces.keys()) == 0

    def test_fail_initdb(self):

        # mock class
        class MockNL(object):

            def __init__(self):
                self.called = set()

            def bind(self, groups=None, async_cache=None):
                self.called.add('bind')
                assert async_cache in (True, False)
                assert isinstance(groups, int)
                raise NotImplementedError('mock thee')

            def clone(self):
                self.called.add('clone')
                self.mnl = type(self)()
                return self.mnl

            def close(self):
                self.called.add('close')

        mock = MockNL()
        try:
            IPDB(nl=mock)
        except NotImplementedError:
            pass

        assert mock.called == set(('clone', ))
        assert mock.mnl.called == set(('bind', 'close'))

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
            assert len(i.interfaces[self.ifname].local_tx) == 0
            i.interfaces[self.ifname].up()
            assert len(i.interfaces[self.ifname].local_tx) == 1
            i.interfaces[self.ifname].drop()
            assert len(i.interfaces[self.ifname].local_tx) == 0

        with IPDB(mode='invalid') as i:
            # transaction mode not supported
            try:
                i.interfaces[self.ifname].up()
            except TypeError:
                pass
