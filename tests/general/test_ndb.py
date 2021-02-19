import os
import csv
import json
import uuid
import time
import random
import threading
from socket import AF_INET
from utils import grep
from utils import require_user
from utils import require_kernel
from utils import skip_if_not_supported
from utils import allocate_network
from utils import free_network
from pyroute2 import config
from pyroute2 import netns
from pyroute2 import NDB
from pyroute2 import IPRoute
from pyroute2 import NetlinkError
from pyroute2.common import uifname
from pyroute2.common import basestring
from pyroute2.common import AF_MPLS
from pyroute2.ndb import report
from pyroute2.ndb.main import (RecordSet,
                               Record)
from pyroute2.ndb.objects import RTNL_Object


class TestMisc(object):

    def test_view_cache(self):
        require_user('root')
        log_id = str(uuid.uuid4())
        ifname1 = uifname()
        ifname2 = uifname()
        with NDB(log='../ndb-%s-%s.log' % (os.getpid(), log_id),
                 rtnl_debug=True) as ndb:
            # the cache is empty from the beginning
            assert len(list(ndb.interfaces.cache)) == 0
            # create test interfaces
            ndb.interfaces.create(ifname=ifname1, kind='dummy').commit()
            ndb.interfaces.create(ifname=ifname2, kind='dummy').commit()
            # the interfaces must not be cached
            assert len(list(ndb.interfaces.cache)) == 0
            # setup the cache expiration time
            ce = config.cache_expire
            config.cache_expire = 1
            # access the interfaces via __getitem__()
            assert ndb.interfaces[ifname1] is not None
            assert ndb.interfaces[ifname2] is not None
            # both must be in the cache
            assert len(list(ndb.interfaces.cache)) == 2
            # expire the cache
            time.sleep(1)
            # access the second interface to trigger the cache invalidation
            assert ndb.interfaces[ifname2] is not None
            # only ifname2 must remain in the cache
            assert len(list(ndb.interfaces.cache)) == 1
            # restore the environment
            config.cache_expire = ce
            ndb.interfaces[ifname1].remove().commit()
            ndb.interfaces[ifname2].remove().commit()

    @skip_if_not_supported
    def test_multiple_sources(self):

        # NB: no 'localhost' record -- important
        #
        sources = [{'target': 'localhost0', 'kind': 'local'},
                   {'target': 'localhost1', 'kind': 'remote'},
                   {'target': 'localhost2', 'kind': 'remote'}]

        # check all the views
        #
        with NDB(sources=sources) as ndb:
            assert len(list(ndb.interfaces.dump()))
            assert len(list(ndb.neighbours.dump()))
            assert len(list(ndb.addresses.dump()))
            assert len(list(ndb.routes.dump()))

        for source in ndb.sources:
            assert ndb.sources[source].nl.closed

    def test_source_localhost_restart(self):
        require_user('root')
        ifname = uifname()

        with NDB() as ndb:
            assert len(list(ndb.interfaces.dump()))
            ndb.sources['localhost'].restart()
            assert len(list(ndb.interfaces.dump()))
            (ndb
             .interfaces
             .create(ifname=ifname, kind='dummy', state='up')
             .commit())
            assert ndb.interfaces[ifname]['state'] == 'up'
            ndb.interfaces[ifname].remove().commit()

    def test_source_netns_restart(self):
        require_user('root')
        ifname = uifname()
        nsname = str(uuid.uuid4())

        with NDB() as ndb:
            ndb.sources.add(netns=nsname)
            assert len(list(ndb.interfaces.dump().filter(target=nsname)))
            ndb.sources[nsname].restart()
            assert len(list(ndb.interfaces.dump().filter(target=nsname)))
            (ndb
             .interfaces
             .create(target=nsname, ifname=ifname, kind='dummy', state='up')
             .commit())
            assert ndb.interfaces[{'target': nsname,
                                   'ifname': ifname}]['state'] == 'up'
            ndb.interfaces[{'target': nsname,
                            'ifname': ifname}].remove().commit()


class TestPreSet(object):

    db_provider = 'sqlite3'
    db_spec = ':memory:'
    nl_class = IPRoute
    nl_kwarg = {}
    ssh = ''
    ipnets = []
    ipranges = []

    def create_interfaces(self):
        # dummy interface
        if_dummy = uifname()
        if_vlan_stag = uifname()
        if_vlan_ctag = uifname()
        if_bridge = uifname()
        if_port = uifname()
        if_addr1 = self.ifaddr()
        if_addr2 = self.ifaddr()
        ret = []

        ret.append(self
                   .ndb
                   .interfaces
                   .create(ifname=if_dummy, kind='dummy')
                   .commit()['index'])

        ret.append(self
                   .ndb
                   .interfaces
                   .create(ifname=if_vlan_stag,
                           link=self.ndb.interfaces[if_dummy]['index'],
                           vlan_id=101,
                           vlan_protocol=0x88a8,
                           kind='vlan')
                   .commit()['index'])

        ret.append(self
                   .ndb
                   .interfaces
                   .create(ifname=if_vlan_ctag,
                           link=self.ndb.interfaces[if_vlan_stag]['index'],
                           vlan_id=1001,
                           vlan_protocol=0x8100,
                           kind='vlan')
                   .commit()['index'])

        ret.append(self
                   .ndb
                   .interfaces
                   .create(ifname=if_bridge, kind='bridge')
                   .set('state', 'up')
                   .commit()['index'])

        ret.append(self
                   .ndb
                   .interfaces
                   .create(ifname=if_port,
                           master=self.ndb.interfaces[if_bridge]['index'],
                           kind='dummy')
                   .commit()['index'])

        (self
         .ndb
         .interfaces[if_bridge]
         .ipaddr
         .create(address=if_addr1, prefixlen=24)
         .commit())

        (self
         .ndb
         .interfaces[if_bridge]
         .ipaddr
         .create(address=if_addr2, prefixlen=24)
         .commit())

        self.if_bridge = if_bridge
        self.if_bridge_addr1 = if_addr1
        self.if_bridge_addr2 = if_addr2

        return ret

    def ifaddr(self, r=0):
        return str(self.ipranges[r].pop())

    def setup(self):
        require_user('root')
        self.log_id = str(uuid.uuid4())
        self.if_simple = None
        self.ipnets = [allocate_network() for _ in range(5)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       log='../ndb-%s-%s.log' % (os.getpid(), self.log_id),
                       rtnl_debug=True)
        self.interfaces = self.create_interfaces()

    def teardown(self):
        with self.nl_class(**self.nl_kwarg) as ipr:
            for link in reversed(self.interfaces):
                ipr.link('del', index=link)
        self.ndb.close()
        for net in self.ipnets:
            free_network(net)

    def fetch(self, request, values=[]):
        return (self
                .ndb
                .schema
                .fetch(request, values))


class AddNS(object):

    def __init__(self):
        self.nsname = str(uuid.uuid4())
        self.ssh = 'ip netns exec %s' % self.nsname


class Basic(object):

    db_provider = 'sqlite3'
    db_spec = ':memory:'
    nl_class = IPRoute
    nl_kwarg = {}
    ssh = ''
    ipnets = []
    ipranges = []
    nsname = None

    def ifaddr(self):
        return str(self.ipranges[0].pop())

    def ifname(self):
        ret = uifname()
        self.interfaces.append(ret)
        return ret

    def getspec(self, **kwarg):
        spec = dict(kwarg)
        if self.nsname is not None:
            spec['target'] = self.nsname
        return spec

    def setup(self):
        require_user('root')
        self.interfaces = []
        self.log_id = str(uuid.uuid4())
        self.ipnets = [allocate_network() for _ in range(2)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       log='../ndb-%s-%s.log' % (os.getpid(), self.log_id),
                       rtnl_debug=True)
        if self.nsname:
            netns.create(self.nsname)
            (self
             .ndb
             .sources
             .add(netns=self.nsname))

    def teardown(self):
        with NDB() as indb:
            if self.nsname:
                (indb
                 .sources
                 .add(netns=self.nsname))
            for link in reversed(self.interfaces):
                try:
                    (indb
                     .interfaces[link]
                     .remove()
                     .commit())
                except Exception:
                    pass
            for link in reversed(self.interfaces):
                try:
                    (indb
                     .interfaces[self.getspec(ifname=link)]
                     .remove()
                     .commit())
                except Exception:
                    pass
        self.ndb.close()
        for net in self.ipnets:
            free_network(net)
        if self.nsname:
            netns.remove(self.nsname)


class TestCreate(Basic):

    def test_context_manager(self):

        ifname = uifname()
        address = '00:11:22:36:47:58'
        spec = self.getspec(ifname=ifname, kind='dummy')
        ifobj = (self
                 .ndb
                 .interfaces
                 .create(**spec))

        with ifobj:
            pass

        assert grep('%s ip link show' % self.ssh, pattern=ifname)

        with ifobj:
            ifobj['state'] = 'up'
            ifobj['address'] = address

        spec = self.getspec(ifname=ifname)
        assert grep('%s ip link show' % self.ssh, pattern=address)
        assert self.ndb.interfaces[spec]['state'] == 'up'

        with ifobj:
            ifobj.remove()

    def test_fail(self):

        ifname = uifname()
        kind = uifname()
        spec = self.getspec(ifname=ifname, kind=kind)

        ifobj = (self
                 .ndb
                 .interfaces
                 .create(**spec))

        save = dict(ifobj)

        try:
            ifobj.commit()
        except NetlinkError as e:
            assert e.code == 95  # Operation not supported

        assert save == dict(ifobj)
        assert ifobj.state == 'invalid'

    def test_veth_simple(self):
        ifname = uifname()
        peername = uifname()
        spec = self.getspec(ifname=ifname,
                            peer=peername,
                            kind='veth')

        (self
         .ndb
         .interfaces
         .create(**spec)
         .commit())

        spec_ifl = self.getspec(ifname=ifname)
        spec_pl = self.getspec(ifname=peername)

        iflink = self.ndb.interfaces[spec_ifl]['link']
        plink = self.ndb.interfaces[spec_pl]['link']

        assert iflink == self.ndb.interfaces[spec_pl]['index']
        assert plink == self.ndb.interfaces[spec_ifl]['index']
        assert grep('%s ip link show' % self.ssh, pattern=ifname)
        assert grep('%s ip link show' % self.ssh, pattern=peername)

        (self
         .ndb
         .interfaces[spec_ifl]
         .remove()
         .commit())

        assert not grep('%s ip link show' % self.ssh, pattern=ifname)
        assert not grep('%s ip link show' % self.ssh, pattern=peername)

    def test_veth_spec(self):
        ifname = uifname()
        peername = uifname()
        nsname = str(uuid.uuid4())

        (self
         .ndb
         .sources
         .add(netns=nsname))

        spec = self.getspec(**{'ifname': ifname,
                               'kind': 'veth',
                               'peer': {'ifname': peername,
                                        'address': '00:11:22:33:44:55',
                                        'net_ns_fd': nsname}})
        (self
         .ndb
         .interfaces
         .create(**spec)
         .commit())

        (self
         .ndb
         .interfaces
         .wait(target=nsname, ifname=peername))

        iflink = (self
                  .ndb
                  .interfaces[self.getspec(ifname=ifname)]['link'])
        plink = (self
                 .ndb
                 .interfaces[{'target': nsname,
                              'ifname': peername}]['link'])

        assert iflink == (self
                          .ndb
                          .interfaces[{'target': nsname,
                                       'ifname': peername}]['index'])
        assert plink == (self
                         .ndb
                         .interfaces[self.getspec(ifname=ifname)]['index'])
        assert grep('%s ip link show' % self.ssh, pattern=ifname)
        assert not grep('%s ip link show' % self.ssh, pattern=peername)

        (self
         .ndb
         .interfaces[self.getspec(ifname=ifname)]
         .remove()
         .commit())

        assert not grep('%s ip link show' % self.ssh, pattern=ifname)
        assert not grep('%s ip link show' % self.ssh, pattern=peername)

        (self
         .ndb
         .sources
         .remove(nsname))

        netns.remove(nsname)

    def test_dummy(self):

        ifname = self.ifname()
        spec = self.getspec(ifname=ifname,
                            kind='dummy',
                            address='00:11:22:33:44:55')
        (self
         .ndb
         .interfaces
         .create(**spec)
         .commit())

        assert grep('%s ip link show' % self.ssh, pattern=ifname)
        assert self.ndb.interfaces[spec]['address'] == '00:11:22:33:44:55'

    def test_bridge(self):

        bridge = self.ifname()
        brport = self.ifname()
        spec_br = self.getspec(ifname=bridge, kind='bridge')
        spec_pt = self.getspec(ifname=brport, kind='dummy')

        (self
         .ndb
         .interfaces
         .create(**spec_br)
         .commit())
        (self
         .ndb
         .interfaces
         .create(**spec_pt)
         .set('master', self.ndb.interfaces[spec_br]['index'])
         .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=bridge)
        assert grep('%s ip link show' % self.ssh,
                    pattern='%s.*%s' % (brport, bridge))

    @skip_if_not_supported
    def test_vrf(self):
        vrf = self.ifname()
        spec = self.getspec(ifname=vrf, kind='vrf')
        (self
         .ndb
         .interfaces
         .create(**spec)
         .set('vrf_table', 42)
         .commit())
        assert grep('%s ip link show' % self.ssh, pattern=vrf)

    def test_vlan(self):
        host = self.ifname()
        vlan = self.ifname()
        spec_host = self.getspec(ifname=host, kind='dummy')
        spec_vlan = self.getspec(ifname=vlan, kind='vlan')
        (self
         .ndb
         .interfaces
         .create(**spec_host)
         .commit())
        (self
         .ndb
         .interfaces
         .create(**spec_vlan)
         .set('link', self.ndb.interfaces[spec_host]['index'])
         .set('vlan_id', 101)
         .commit())
        assert grep('%s ip link show' % self.ssh, pattern=vlan)

    def test_vxlan(self):
        host = self.ifname()
        vxlan = self.ifname()
        spec_host = self.getspec(ifname=host, kind='dummy')
        spec_vxlan = self.getspec(ifname=vxlan, kind='vxlan')
        (self
         .ndb
         .interfaces
         .create(**spec_host)
         .commit())
        (self
         .ndb
         .interfaces
         .create(**spec_vxlan)
         .set('vxlan_link', self.ndb.interfaces[spec_host]['index'])
         .set('vxlan_id', 101)
         .set('vxlan_group', '239.1.1.1')
         .set('vxlan_ttl', 16)
         .commit())
        assert grep('%s ip link show' % self.ssh, pattern=vxlan)

    def test_basic_address(self):

        ifaddr = self.ifaddr()
        ifname = self.ifname()
        spec_if = self.getspec(ifname=ifname, kind='dummy', state='up')
        i = (self
             .ndb
             .interfaces
             .create(**spec_if))
        i.commit()

        spec_ad = self.getspec(index=i['index'], address=ifaddr, prefixlen=24)
        a = (self
             .ndb
             .addresses
             .create(**spec_ad))
        a.commit()
        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)


class TestCreateNS(AddNS, TestCreate):
    pass


class TestRoutesMPLS(Basic):

    def get_mpls_routes(self):
        return len(tuple(self
                         .ndb
                         .routes
                         .getmany({'family': AF_MPLS})))

    @skip_if_not_supported
    def test_via_ipv4(self):
        require_kernel(4, 4)
        require_user('root')

        ifname = self.ifname()
        ifaddr = self.ifaddr()
        router = self.ifaddr()

        if_spec = self.getspec(ifname=ifname,
                               kind='dummy',
                               state='up')

        l1 = self.get_mpls_routes()

        i = (self
             .ndb
             .interfaces
             .create(**if_spec)
             .add_ip('%s/24' % (ifaddr, ))
             .commit())

        rt_spec = self.getspec(family=AF_MPLS,
                               oif=i['index'],
                               via={'family': AF_INET, 'addr': router},
                               newdst={'label': 0x20})

        rt = (self
              .ndb
              .routes
              .create(**rt_spec)
              .commit())

        l2 = self.get_mpls_routes()
        assert l2 > l1
        rt.remove().commit()
        l3 = self.get_mpls_routes()
        assert l3 < l2
        assert rt.state == 'invalid'

    @skip_if_not_supported
    def test_encap_mpls(self):
        require_kernel(4, 4)
        require_user('root')

        ifname = self.ifname()
        ifaddr = self.ifaddr()
        gateway = self.ifaddr()

        if_spec = self.getspec(ifname=ifname,
                               kind='dummy',
                               state='up')

        (self
         .ndb
         .interfaces
         .create(**if_spec)
         .add_ip('%s/24' % (ifaddr, ))
         .commit())

        rt_spec = self.getspec(dst='%s/24' % (self.ipranges[1][0], ),
                               gateway=gateway,
                               encap={'type': 'mpls', 'labels': [20, 30]})
        (self
         .ndb
         .routes
         .create(**rt_spec)
         .commit())


class TestRoutes(Basic):
    table = None

    def test_basic(self):

        ifaddr = self.ifaddr()
        router = self.ifaddr()
        ifname = self.ifname()
        i = (self
             .ndb
             .interfaces
             .create(self.getspec(ifname=ifname, kind='dummy', state='up')))
        i.commit()

        a = (self
             .ndb
             .addresses
             .create(self.getspec(index=i['index'],
                                  address=ifaddr,
                                  prefixlen=24)))
        a.commit()

        spec = {'dst_len': 24,
                'dst': str(self.ipnets[1].network),
                'gateway': router}

        if self.table:
            spec['table'] = self.table

        r = (self
             .ndb
             .routes
             .create(self.getspec(**spec)))

        r.commit()
        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*%s' % (str(self.ipnets[1]), ifname))

    def _test_metrics_update(self, method):

        ifaddr = self.ifaddr()
        gateway1 = self.ifaddr()
        ifname = self.ifname()
        i = (self
             .ndb
             .interfaces
             .create(self.getspec(ifname=ifname, kind='dummy', state='up')))
        i.commit()

        a = (self
             .ndb
             .addresses
             .create(self.getspec(index=i['index'],
                                  address=ifaddr,
                                  prefixlen=24)))
        a.commit()

        spec = {'dst_len': 24,
                'dst': str(self.ipnets[1].network),
                'gateway': gateway1,
                'metrics': {'mtu': 1300}}

        if self.table:
            spec['table'] = self.table

        r = (self
             .ndb
             .routes
             .create(self.getspec(**spec)))

        r.commit()
        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*%s.*%s.*mtu 1300' % (str(self.ipnets[1]),
                                                      gateway1, ifname))

        r['metrics']['mtu'] = 1500
        getattr(r, method)()

        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*%s.*%s.*mtu 1500' % (str(self.ipnets[1]),
                                                      gateway1, ifname))

    def test_metrics_update_apply(self):
        return self._test_metrics_update('apply')

    def test_metrics_update_commit(self):
        return self._test_metrics_update('commit')

    def test_default(self):

        ifaddr = self.ifaddr()
        router = self.ifaddr()
        ifname = self.ifname()
        random.seed()
        tnum = random.randint(500, 600)

        (self
         .ndb
         .interfaces
         .create(self.getspec(ifname=ifname, kind='dummy', state='up'))
         .add_ip('%s/24' % ifaddr)
         .commit())

        spec = {'dst': 'default',
                'gateway': router}

        if self.table:
            spec['table'] = self.table
        else:
            spec['table'] = tnum

        (self
         .ndb
         .routes
         .create(self.getspec(**spec))
         .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or tnum),
                    pattern=router)

    def test_update_set(self):
        ifaddr = self.ifaddr()
        router1 = self.ifaddr()
        router2 = self.ifaddr()
        ifname = self.ifname()
        network = str(self.ipnets[1].network)

        (self
         .ndb
         .interfaces
         .create(self.getspec(ifname=ifname, kind='dummy', state='up'))
         .ipaddr
         .create(address=ifaddr, prefixlen=24)
         .commit())

        spec = {'dst_len': 24,
                'dst': network,
                'gateway': router1}

        if self.table:
            spec['table'] = self.table

        r = (self
             .ndb
             .routes
             .create(self.getspec(**spec))
             .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*via %s.*%s' % (network, router1, ifname))

        r.set('gateway', router2).commit()

        assert not grep('%s ip route show table %i' % (self.ssh,
                                                       self.table or 254),
                        pattern='%s.*via %s.*%s' % (network, router1, ifname))
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*via %s.*%s' % (network, router2, ifname))

    def test_update_replace(self):
        ifaddr = self.ifaddr()
        router = self.ifaddr()
        ifname = self.ifname()
        network = str(self.ipnets[1].network)

        (self
         .ndb
         .interfaces
         .create(self.getspec(ifname=ifname, kind='dummy', state='up'))
         .ipaddr
         .create(address=ifaddr, prefixlen=24)
         .commit())

        spec = {'dst_len': 24,
                'dst': network,
                'priority': 10,
                'gateway': router}

        if self.table:
            spec['table'] = self.table

        r = (self
             .ndb
             .routes
             .create(self.getspec(**spec))
             .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*%s.*metric %s' % (network, ifname, 10))

        r.set('priority', 15).commit()

        assert not grep('%s ip route show table %i' % (self.ssh,
                                                       self.table or 254),
                        pattern='%s.*%s.*metric %s' % (network, ifname, 10))
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s.*%s.*metric %s' % (network, ifname, 15))

    def test_multipath_ipv4(self):

        ifname = self.ifname()
        ifaddr = self.ifaddr()
        hop1 = self.ifaddr()
        hop2 = self.ifaddr()

        (self
         .ndb
         .interfaces
         .create(self.getspec(ifname=ifname, kind='dummy', state='up'))
         .ipaddr
         .create(address=ifaddr, prefixlen=24)
         .commit())

        spec = {'dst_len': 24,
                'dst': str(self.ipnets[1].network),
                'multipath': [{'gateway': hop1},
                              {'gateway': hop2}]}

        if self.table:
            spec['table'] = self.table

        (self
         .ndb
         .routes
         .create(**self.getspec(**spec))
         .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='%s' % str(self.ipnets[1]))
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='nexthop.*%s.*%s' % (hop1, ifname))
        assert grep('%s ip route show table %i' % (self.ssh,
                                                   self.table or 254),
                    pattern='nexthop.*%s.*%s' % (hop2, ifname))


class TestRoutes_501(TestRoutes):
    table = 501


class TestRoutes_6001(TestRoutes):
    table = 6001


class TestRoutesNS(AddNS, TestRoutes):
    pass


class TestRoutesNS_501(TestRoutesNS):
    table = 501


class TestRoutesNS_6001(TestRoutesNS):
    table = 6001


class TestAddress(Basic):

    def test_add_del_ip_dict(self):
        ifname = self.ifname()
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()

        (self
         .ndb
         .interfaces
         .create(self.getspec(ifname=ifname, kind='dummy', state='down'))
         .add_ip({'address': ifaddr1, 'prefixlen': 24})
         .add_ip({'address': ifaddr2, 'prefixlen': 24})
         .commit())

        assert grep('%s ip -o addr show' % self.ssh,
                    pattern='%s.*%s' % (ifname, ifaddr1))
        assert grep('%s ip -o addr show' % self.ssh,
                    pattern='%s.*%s' % (ifname, ifaddr2))

        (self
         .ndb
         .interfaces[self.getspec(ifname=ifname)]
         .del_ip({'address': ifaddr2, 'prefixlen': 24})
         .del_ip({'address': ifaddr1, 'prefixlen': 24})
         .commit())

        assert not grep('%s ip -o addr show' % self.ssh,
                        pattern='%s.*%s' % (ifname, ifaddr1))
        assert not grep('%s ip -o addr show' % self.ssh,
                        pattern='%s.*%s' % (ifname, ifaddr2))

    def test_add_del_ip_string(self):
        ifname = self.ifname()
        ifaddr1 = '%s/24' % (self.ifaddr())
        ifaddr2 = '%s/24' % (self.ifaddr())

        (self
         .ndb
         .interfaces
         .create(self.getspec(ifname=ifname, kind='dummy', state='down'))
         .add_ip(ifaddr1)
         .add_ip(ifaddr2)
         .commit())

        assert grep('%s ip -o addr show' % self.ssh,
                    pattern='%s.*%s' % (ifname, ifaddr1))
        assert grep('%s ip -o addr show' % self.ssh,
                    pattern='%s.*%s' % (ifname, ifaddr2))

        (self
         .ndb
         .interfaces[self.getspec(ifname=ifname)]
         .del_ip(ifaddr2)
         .del_ip(ifaddr1)
         .commit())

        assert not grep('%s ip -o addr show' % self.ssh,
                        pattern='%s.*%s' % (ifname, ifaddr1))
        assert not grep('%s ip -o addr show' % self.ssh,
                        pattern='%s.*%s' % (ifname, ifaddr2))


class TestAddressNS(AddNS, TestAddress):
    pass


class TestBridge(Basic):

    def get_stp(self, name):
        with open('/sys/class/net/%s/bridge/stp_state' % name, 'r') as f:
            return int(f.read())

    def _test_stp_link(self, state, cond):
        bridge = self.ifname()

        r = (self
             .ndb
             .interfaces
             .create(ifname=bridge,
                     kind='bridge',
                     br_stp_state=0,
                     state=state)
             .commit())

        assert self.get_stp(bridge) == 0
        assert r['state'] == state
        assert cond(r['flags'])

        (self
         .ndb
         .interfaces[bridge]
         .set('br_stp_state', 1)
         .commit())

        assert self.get_stp(bridge) == 1
        assert r['br_stp_state'] == 1

        (self
         .ndb
         .interfaces[bridge]
         .set('br_stp_state', 0)
         .commit())

        assert self.get_stp(bridge) == 0
        assert r['br_stp_state'] == 0

    def test_stp_link_up(self):
        self._test_stp_link('up', lambda x: x % 2 != 0)

    def test_stp_link_down(self):
        self._test_stp_link('down', lambda x: x % 2 == 0)

    def test_manage_ports(self):
        bridge = self.ifname()
        brport1 = self.ifname()
        brport2 = self.ifname()

        (self
         .ndb
         .interfaces
         .create(ifname=brport1, kind='dummy')
         .commit())
        (self
         .ndb
         .interfaces
         .create(ifname=brport2, kind='dummy')
         .commit())
        (self
         .ndb
         .interfaces
         .create(ifname=bridge, kind='bridge')
         .add_port(brport1)
         .add_port(brport2)
         .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=bridge)
        assert grep('%s ip link show' % self.ssh,
                    pattern='%s.*master %s' % (brport1, bridge))
        assert grep('%s ip link show' % self.ssh,
                    pattern='%s.*master %s' % (brport2, bridge))

        (self
         .ndb
         .interfaces[bridge]
         .del_port(brport1)
         .del_port(brport2)
         .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=brport1)
        assert grep('%s ip link show' % self.ssh,
                    pattern=brport2)
        assert not grep('%s ip link show' % self.ssh,
                        pattern='%s.*master %s' % (brport1, bridge))
        assert not grep('%s ip link show' % self.ssh,
                        pattern='%s.*master %s' % (brport2, bridge))


class TestNetNS(object):

    db_provider = 'sqlite3'
    db_spec = ':memory:'

    def setup(self):
        require_user('root')
        self.log_id = str(uuid.uuid4())
        self.netns = str(uuid.uuid4())
        self.ipnets = [allocate_network() for _ in range(3)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.sources = [{'target': 'localhost'},
                        {'netns': self.netns},
                        {'target': 'localhost/netns',
                         'kind': 'nsmanager'}]
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       sources=self.sources,
                       log='../ndb-%s-%s.log' % (os.getpid(), self.log_id),
                       rtnl_debug=True,
                       auto_netns=True)

    def ifaddr(self, r=0):
        return str(self.ipranges[r].pop())

    def teardown(self):
        for net in self.ipnets:
            free_network(net)
        self.ndb.close()
        netns.remove(self.netns)

    def test_nsmanager(self):
        assert self.ndb.netns.count() > 0

    def test_auto_netns(self):
        newns = str(uuid.uuid4())
        assert self.ndb.interfaces.count() > 0
        assert len(tuple(self
                         .ndb
                         .interfaces
                         .summary()
                         .filter(target='netns/%s' % newns))) == 0
        netns.create(newns)
        self.ndb.interfaces.wait(**{'target': 'netns/%s' % newns})
        netns.remove(newns)

    def test_basic(self):
        ifname = uifname()
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        ifaddr3 = self.ifaddr()

        (self
         .ndb
         .interfaces
         .create(target=self.netns, ifname=ifname, kind='dummy')
         .ipaddr
         .create(address=ifaddr1, prefixlen=24)
         .create(address=ifaddr2, prefixlen=24)
         .create(address=ifaddr3, prefixlen=24)
         .commit())

        with NDB(sources=[{'target': 'localhost',
                           'netns': self.netns,
                           'kind': 'netns'}]) as ndb:
            if_idx = ndb.interfaces[ifname]['index']
            addr1_idx = ndb.addresses['%s/24' % ifaddr1]['index']
            addr2_idx = ndb.addresses['%s/24' % ifaddr2]['index']
            addr3_idx = ndb.addresses['%s/24' % ifaddr3]['index']

        assert if_idx == addr1_idx == addr2_idx == addr3_idx

    def _assert_test_view(self, ifname, ifaddr):
        with NDB(sources=[{'target': 'localhost',
                           'netns': self.netns,
                           'kind': 'netns'}]) as ndb:
            (if_idx,
             if_state,
             if_addr,
             if_flags) = ndb.interfaces[ifname].fields('index',
                                                       'state',
                                                       'address',
                                                       'flags')
            addr_idx = ndb.addresses['%s/24' % ifaddr]['index']

        assert if_idx == addr_idx
        assert if_state == 'up'
        assert if_flags & 1
        assert if_addr == '00:11:22:33:44:55'

    def test_move(self):
        ifname = uifname()
        ifaddr = self.ifaddr()
        # create the interfaces
        (self
         .ndb
         .interfaces
         .create(ifname=ifname, kind='dummy')
         .commit())
        # move it to a netns
        (self
         .ndb
         .interfaces[ifname]
         .set('net_ns_fd', self.netns)
         .commit())
        # setup the interface only when it is moved
        (self
         .ndb
         .interfaces
         .wait(target=self.netns, ifname=ifname)
         .set('state', 'up')
         .set('address', '00:11:22:33:44:55')
         .ipaddr
         .create(address=ifaddr, prefixlen=24)
         .commit())
        self._assert_test_view(ifname, ifaddr)


class TestRollback(TestPreSet):

    def setup(self):
        require_user('root')
        self.log_id = str(uuid.uuid4())
        self.ipnets = [allocate_network() for _ in range(5)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       log='../ndb-%s-%s.log' % (os.getpid(), self.log_id),
                       rtnl_debug=True)
        self.interfaces = []

    def test_simple_deps(self):

        # register NDB handler to wait for the interface
        self.if_simple = uifname()

        ifaddr = self.ifaddr()
        router = self.ifaddr()
        dst = str(self.ipnets[1].network)

        #
        # simple dummy interface with one address and
        # one dependent route
        #
        (self
         .interfaces
         .append(self
                 .ndb
                 .interfaces
                 .create(ifname=self.if_simple, kind='dummy')
                 .set('state', 'up')
                 .commit()['index']))
        (self
         .ndb
         .addresses
         .create(address=ifaddr,
                 prefixlen=24,
                 index=self.interfaces[-1])
         .commit())

        (self
         .ndb
         .routes
         .create(dst=dst, dst_len=24, gateway=router)
         .commit())

        iface = self.ndb.interfaces[self.if_simple]
        # check everything is in place
        assert grep('%s ip link show' % self.ssh, pattern=self.if_simple)
        assert grep('%s ip route show' % self.ssh, pattern=self.if_simple)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (dst, router))

        # remove the interface
        iface.remove()
        iface.commit()

        # check there is no interface, no route
        assert not grep('%s ip link show' % self.ssh, pattern=self.if_simple)
        assert not grep('%s ip route show' % self.ssh, pattern=self.if_simple)
        assert not grep('%s ip route show' % self.ssh,
                        pattern='%s.*%s' % (dst, router))

        # revert the changes using the implicit last_save
        iface.rollback()
        assert grep('%s ip link show' % self.ssh, pattern=self.if_simple)
        assert grep('%s ip route show' % self.ssh, pattern=self.if_simple)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (dst, router))

    def test_bridge_deps(self):

        self.if_br0 = uifname()
        self.if_br0p0 = uifname()
        self.if_br0p1 = uifname()
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        router = self.ifaddr()
        dst = str(self.ipnets[1].network)

        (self
         .interfaces
         .append(self
                 .ndb
                 .interfaces
                 .create(ifname=self.if_br0,
                         kind='bridge',
                         state='up')
                 .commit()['index']))
        (self
         .interfaces
         .append(self
                 .ndb
                 .interfaces
                 .create(ifname=self.if_br0p0,
                         kind='dummy',
                         state='up',
                         master=self.ndb.interfaces[self.if_br0]['index'])
                 .commit()['index']))
        (self
         .interfaces
         .append(self
                 .ndb
                 .interfaces
                 .create(ifname=self.if_br0p1,
                         kind='dummy',
                         state='up',
                         master=self.ndb.interfaces[self.if_br0]['index'])
                 .commit()['index']))
        (self
         .ndb
         .interfaces[self.if_br0]
         .ipaddr
         .create(address=ifaddr1, prefixlen=24)
         .commit())
        (self
         .ndb
         .interfaces[self.if_br0]
         .ipaddr
         .create(address=ifaddr2, prefixlen=24)
         .commit())
        (self
         .ndb
         .routes
         .create(dst=dst, dst_len=24, gateway=router)
         .commit())

        master = self.ndb.interfaces[self.if_br0]['index']
        self.ndb.interfaces.wait(ifname=self.if_br0p0, master=master)
        self.ndb.interfaces.wait(ifname=self.if_br0p1, master=master)
        self.ndb.addresses.wait(address=ifaddr1)
        self.ndb.addresses.wait(address=ifaddr2)
        self.ndb.routes.wait(dst=dst, gateway=router)
        iface = self.ndb.interfaces[self.if_br0]
        # check everything is in place
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0)
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0p0)
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0p1)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr1)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr2)
        assert grep('%s ip route show' % self.ssh, pattern=self.if_br0)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (dst, router))

        # remove the interface
        iface.remove()
        iface.commit()

        # check there is no interface, no route
        assert not grep('%s ip link show' % self.ssh, pattern=self.if_br0)
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0p0)
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0p1)
        assert not grep('%s ip addr show' % self.ssh, pattern=ifaddr1)
        assert not grep('%s ip addr show' % self.ssh, pattern=ifaddr2)
        assert not grep('%s ip route show' % self.ssh, pattern=self.if_br0)
        assert not grep('%s ip route show' % self.ssh,
                        pattern='%s.*%s' % (dst, router))

        # revert the changes using the implicit last_save
        iface.rollback()
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0)
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0p0)
        assert grep('%s ip link show' % self.ssh, pattern=self.if_br0p1)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr1)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr2)
        assert grep('%s ip route show' % self.ssh, pattern=self.if_br0)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (dst, router))

    def test_vlan_deps(self):

        if_host = uifname()
        if_vlan = uifname()
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        router = self.ifaddr()
        dst = str(self.ipnets[1].network)

        (self
         .interfaces
         .append(self
                 .ndb
                 .interfaces
                 .create(ifname=if_host,
                         kind='dummy',
                         state='up')
                 .commit()['index']))
        (self
         .interfaces
         .append(self
                 .ndb
                 .interfaces
                 .create(ifname=if_vlan,
                         kind='vlan',
                         link=self.interfaces[-1],
                         state='up',
                         vlan_id=1001)
                 .commit()['index']))
        (self
         .ndb
         .addresses
         .create(address=ifaddr1,
                 prefixlen=24,
                 index=self.interfaces[-1])
         .commit())
        (self
         .ndb
         .addresses
         .create(address=ifaddr2,
                 prefixlen=24,
                 index=self.interfaces[-1])
         .commit())
        (self
         .ndb
         .routes
         .create(dst=dst, dst_len=24, gateway=router)
         .commit())

        iface = self.ndb.interfaces[if_host]
        # check everything is in place
        assert grep('%s ip link show' % self.ssh, pattern=if_host)
        assert grep('%s ip link show' % self.ssh, pattern=if_vlan)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr1)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr2)
        assert grep('%s ip route show' % self.ssh, pattern=if_vlan)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (dst, router))
        assert grep('%s cat /proc/net/vlan/config' % self.ssh, pattern=if_vlan)

        # remove the interface
        iface.remove()
        iface.commit()

        # check there is no interface, no route
        assert not grep('%s ip link show' % self.ssh, pattern=if_host)
        assert not grep('%s ip link show' % self.ssh, pattern=if_vlan)
        assert not grep('%s ip addr show' % self.ssh, pattern=ifaddr1)
        assert not grep('%s ip addr show' % self.ssh, pattern=ifaddr2)
        assert not grep('%s ip route show' % self.ssh, pattern=if_vlan)
        assert not grep('%s ip route show' % self.ssh,
                        pattern='%s.*%s' % (dst, router))
        assert not grep('%s cat /proc/net/vlan/config' % self.ssh,
                        pattern=if_vlan)

        # revert the changes using the implicit last_save
        iface.rollback()
        assert grep('%s ip link show' % self.ssh, pattern=if_host)
        assert grep('%s ip link show' % self.ssh, pattern=if_vlan)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr1)
        assert grep('%s ip addr show' % self.ssh, pattern=ifaddr2)
        assert grep('%s ip route show' % self.ssh, pattern=if_vlan)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (dst, router))
        assert grep('%s cat /proc/net/vlan/config' % self.ssh, pattern=if_vlan)


class TestSchema(TestPreSet):

    def test_basic(self):
        assert len(set(self.interfaces) -
                   set([x[0] for x in
                        self.fetch('select f_index from interfaces')])) == 0

    def _test_vlan_interfaces(self):
        assert len(tuple(self.fetch('select * from vlan'))) >= 2

    def _test_bridge_interfaces(self):
        assert len(tuple(self.fetch('select * from bridge'))) >= 1


class TestSources(TestPreSet):

    def count_interfaces(self, target):
        return (self
                .ndb
                .schema
                .fetchone('''
                          SELECT count(*) FROM interfaces
                          WHERE f_target = '%s'
                          ''' % target))[0]

    def test_connect_netns(self):
        nsname = str(uuid.uuid4())
        with self.ndb.readonly:
            s = len(list(self.ndb.interfaces.summary()))
            assert self.count_interfaces(nsname) == 0
            assert self.count_interfaces('localhost') <= s

        # connect RTNL source
        event = threading.Event()
        self.ndb.sources.add(**{'target': nsname,
                                'kind': 'netns',
                                'netns': nsname,
                                'event': event})
        assert event.wait(5)

        with self.ndb.readonly:
            s = len(list(self.ndb.interfaces.summary()))
            assert self.count_interfaces(nsname) > 0
            assert self.count_interfaces('localhost') < s

        # disconnect the source
        self.ndb.sources[nsname].close()
        with self.ndb.readonly:
            s = len(list(self.ndb.interfaces.summary()))
            assert self.count_interfaces(nsname) == 0
            assert self.count_interfaces('localhost') <= s

        netns.remove(nsname)

    def test_disconnect_localhost(self):
        with self.ndb.readonly:
            s = len(list(self.ndb.interfaces.summary()))
            assert self.count_interfaces('localhost') <= s

        self.ndb.sources.remove('localhost')

        with self.ndb.readonly:
            s = len(list(self
                         .ndb
                         .interfaces
                         .summary()
                         .filter(target='localhost')))
            assert self.count_interfaces('localhost') == s
            assert s == 0


class MD(csv.Dialect):
    quotechar = "'"
    doublequote = False
    quoting = csv.QUOTE_MINIMAL
    delimiter = ","
    lineterminator = "\n"


class TestReports(TestPreSet):

    def test_types(self):
        save = report.MAX_REPORT_LINES
        report.MAX_REPORT_LINES = 1
        # check for the report type here
        assert isinstance(self.ndb.interfaces.summary(), RecordSet)
        # repr must be a string
        assert isinstance(repr(self.ndb.interfaces.summary()), basestring)
        # header + MAX_REPORT_LINES + (...)
        assert len(repr(self.ndb.interfaces.summary()).split('\n')) == 3
        report.MAX_REPORT_LINES = save

    def test_iter_keys(self):
        for name in ('interfaces',
                     'addresses',
                     'neighbours',
                     'routes',
                     'rules'):
            view = getattr(self.ndb, name)
            for key in view:
                assert isinstance(key, Record)
                obj = view.get(key)
                if obj is not None:
                    assert isinstance(obj, RTNL_Object)

    def test_join(self):
        addr = (self
                .ndb
                .addresses
                .dump()
                .filter(lambda x: x.family == AF_INET)
                .join((self
                       .ndb
                       .interfaces
                       .dump()
                       .filter(lambda x: x.state == 'up')),
                      condition=lambda l, r: l.index == r.index and
                      r.ifname == self.if_bridge,
                      prefix='if_')
                .select('address'))

        s1 = set((self.if_bridge_addr1, self.if_bridge_addr2))
        s2 = set([x.address for x in addr])
        assert s1 == s2

    def test_slices(self):
        a = list(self.ndb.rules.dump())
        ln = len(a) - 1
        # simple indices
        assert a[0] == self.ndb.rules.dump()[0]
        assert a[1] == self.ndb.rules.dump()[1]
        assert a[-1] == self.ndb.rules.dump()[-1]
        assert self.ndb.rules.dump()[ln] == a[-1]
        try:
            self.ndb.rules.dump()[len(a)]
        except IndexError:
            pass
        # slices
        assert a[0:] == self.ndb.rules.dump()[0:]
        assert a[:3] == self.ndb.rules.dump()[:3]
        assert a[0:3] == self.ndb.rules.dump()[0:3]
        assert a[1:3] == self.ndb.rules.dump()[1:3]
        # negative slices
        assert a[-3:] == self.ndb.rules.dump()[-3:]
        assert a[-3:-1] == self.ndb.rules.dump()[-3:-1]
        # mixed
        assert a[-ln:ln - 1] == self.ndb.rules.dump()[-ln:ln - 1]
        # step
        assert a[2:ln:2] == self.ndb.rules.dump()[2:ln:2]

    @skip_if_not_supported
    def test_report_chains(self):
        ipnet = allocate_network()
        ifaddr = tuple(self
                       .ndb
                       .addresses
                       .summary()
                       .filter(ifname=self.if_bridge, prefixlen=24)
                       .select('address'))[0].address

        (self
         .ndb
         .routes
         .create(dst=str(ipnet),
                 gateway=ifaddr,
                 encap={'type': 'mpls', 'labels': [20, 30]})
         .commit())

        encap = tuple(self
                      .ndb
                      .routes
                      .dump()
                      .filter(oif=self.ndb.interfaces[self.if_bridge]['index'])
                      .filter(lambda x: x.encap is not None)
                      .select('encap')
                      .transform(encap=lambda x: json.loads(x)))[0].encap

        assert isinstance(encap, list)
        assert encap[0]['label'] == 20
        assert encap[0]['bos'] == 0
        assert encap[1]['label'] == 30
        assert encap[1]['bos'] == 1

    def test_json(self):
        data = json.loads(''.join(self
                                  .ndb
                                  .interfaces
                                  .summary()
                                  .format('json')))
        assert isinstance(data, list)
        for row in data:
            assert isinstance(row, dict)

    def test_csv(self):
        record_length = 0

        for record in self.ndb.routes.dump():
            if record_length == 0:
                record_length = len(record)
            else:
                assert len(record) == record_length

        reader = csv.reader(self
                            .ndb
                            .routes
                            .dump()
                            .format('csv'), dialect=MD())
        for record in reader:
            assert len(record) == record_length

    def test_nested_ipaddr(self):
        records = repr(self
                       .ndb
                       .interfaces[self.if_bridge]
                       .ipaddr
                       .dump()
                       .filter(lambda x: x.family == AF_INET))
        rlen = len(records.split('\n'))
        # 2 ipaddr
        assert rlen == 2

    def test_nested_ports(self):
        records = len(repr(self
                           .ndb
                           .interfaces[self.if_bridge]
                           .ports
                           .summary()).split('\n'))
        # 1 port
        assert records == 1
