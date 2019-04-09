import os
import uuid
import threading
from utils import grep
from utils import require_user
from utils import skip_if_not_supported
from utils import allocate_network
from utils import free_network
from pyroute2 import netns
from pyroute2 import NDB
from pyroute2 import NetNS
from pyroute2 import IPRoute
from pyroute2 import NetlinkError
from pyroute2 import RemoteIPRoute
from pyroute2.common import uifname
from pyroute2.common import basestring
from pyroute2.ndb import report
from pyroute2.ndb.main import Report


class TestMisc(object):

    @skip_if_not_supported
    def test_multiple_sources(self):

        # NB: no 'localhost' record -- important
        #
        sources = {'localhost0': {'class': IPRoute},
                   'localhost1': {'class': RemoteIPRoute},  # local mitogen
                   'localhost2': {'class': RemoteIPRoute}}  # one more

        # check all the views
        #
        with NDB(sources=sources) as ndb:
            assert len(ndb.interfaces.csv())
            assert len(ndb.neighbours.csv())
            assert len(ndb.addresses.csv())
            assert len(ndb.routes.csv())

        for source in ndb.sources:
            assert ndb.sources[source].nl.closed


class TestBase(object):

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

        with self.nl_class(**self.nl_kwarg) as ipr:

            ipr.link('add',
                     ifname=if_dummy,
                     kind='dummy')
            self.ndb.wait({'interfaces': [{'ifname': if_dummy}]})
            ret.append(self.ndb.interfaces[if_dummy]['index'])

            ipr.link('add',
                     ifname=if_vlan_stag,
                     link=self.ndb.interfaces[if_dummy]['index'],
                     vlan_id=101,
                     vlan_protocol=0x88a8,
                     kind='vlan')
            self.ndb.wait({'interfaces': [{'ifname': if_vlan_stag}]})
            ret.append(self.ndb.interfaces[if_vlan_stag]['index'])

            ipr.link('add',
                     ifname=if_vlan_ctag,
                     link=self.ndb.interfaces[if_vlan_stag]['index'],
                     vlan_id=1001,
                     vlan_protocol=0x8100,
                     kind='vlan')
            self.ndb.wait({'interfaces': [{'ifname': if_vlan_ctag}]})
            ret.append(self.ndb.interfaces[if_vlan_ctag]['index'])

            ipr.link('add',
                     ifname=if_port,
                     kind='dummy')
            self.ndb.wait({'interfaces': [{'ifname': if_port}]})
            ret.append(self.ndb.interfaces[if_port]['index'])

            ipr.link('add',
                     ifname=if_bridge,
                     kind='bridge')
            self.ndb.wait({'interfaces': [{'ifname': if_bridge}]})
            ipr.link('set',
                     index=self.ndb.interfaces[if_port]['index'],
                     master=self.ndb.interfaces[if_bridge]['index'])
            ret.append(self.ndb.interfaces[if_bridge]['index'])
            ipr.addr('add',
                     index=self.ndb.interfaces[if_bridge]['index'],
                     address=if_addr1,
                     prefixlen=24)
            ipr.addr('add',
                     index=self.ndb.interfaces[if_bridge]['index'],
                     address=if_addr2,
                     prefixlen=24)
            self.ndb.wait({'addresses': [{'address': if_addr1},
                                         {'address': if_addr2}]})
            self.if_bridge = if_bridge
            return ret

    def ifaddr(self, r=0):
        return str(self.ipranges[r].pop())

    def setup(self):
        require_user('root')
        self.if_simple = None
        self.ipnets = [allocate_network() for _ in range(5)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.nl_kwarg['class'] = self.nl_class
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       rtnl_log=True,
                       sources={'localhost': self.nl_kwarg})
        self.ndb.debug('../ndb-%s-%s.log' % (os.getpid(), id(self.ndb)))
        self.interfaces = self.create_interfaces()

    def teardown(self):
        with self.nl_class(**self.nl_kwarg) as ipr:
            for link in reversed(self.interfaces):
                ipr.link('del', index=link)
        self.ndb.close()
        for net in self.ipnets:
            free_network(net)

    def fetch(self, request, values=[]):
        with self.ndb.schema.db_lock:
            return (self
                    .ndb
                    .schema
                    .execute(request, values)
                    .fetchall())


class TestCreate(object):

    db_provider = 'sqlite3'
    db_spec = ':memory:'
    nl_class = IPRoute
    nl_kwarg = {}
    ssh = ''
    ipnets = []
    ipranges = []

    def ifaddr(self):
        return str(self.ipranges[0].pop())

    def ifname(self):
        ret = uifname()
        self.interfaces.append(ret)
        return ret

    def setup(self):
        require_user('root')
        self.interfaces = []
        self.ipnets = [allocate_network() for _ in range(2)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.nl_kwarg['class'] = self.nl_class
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       rtnl_log=True,
                       sources={'localhost': self.nl_kwarg})
        self.ndb.debug('../ndb-%s-%s.log' % (os.getpid(), id(self.ndb)))

    def teardown(self):
        with self.nl_class(**self.nl_kwarg) as ipr:
            for link in reversed(self.interfaces):
                ipr.link('del', index=ipr.link_lookup(ifname=link)[0])
        self.ndb.close()
        for net in self.ipnets:
            free_network(net)

    def test_context_manager(self):

        ifname = uifname()
        address = '00:11:22:36:47:58'
        ifobj = (self
                 .ndb
                 .interfaces
                 .add(ifname=ifname, kind='dummy'))

        with ifobj:
            pass

        assert grep('%s ip link show' % self.ssh, pattern=ifname)

        with ifobj:
            ifobj['state'] = 'up'
            ifobj['address'] = address

        assert grep('%s ip link show' % self.ssh, pattern=address)
        assert self.ndb.interfaces[ifname]['state'] == 'up'

        with ifobj:
            ifobj.remove()

    def test_fail(self):

        ifname = uifname()
        kind = uifname()

        ifobj = (self
                 .ndb
                 .interfaces
                 .add(ifname=ifname, kind=kind))

        save = dict(ifobj)

        try:
            ifobj.commit()
        except NetlinkError as e:
            assert e.code == 95  # Operation not supported

        assert save == dict(ifobj)
        assert ifobj.state == 'invalid'

    def test_dummy(self):

        ifname = self.ifname()
        (self
         .ndb
         .interfaces
         .add(ifname=ifname, kind='dummy', address='00:11:22:33:44:55')
         .commit())

        assert grep('%s ip link show' % self.ssh, pattern=ifname)
        assert self.ndb.interfaces[ifname]['address'] == '00:11:22:33:44:55'

    def test_bridge(self):

        bridge = self.ifname()
        brport = self.ifname()

        (self
         .ndb
         .interfaces
         .add(ifname=bridge, kind='bridge')
         .commit())
        (self
         .ndb
         .interfaces
         .add(ifname=brport, kind='dummy')
         .set('master', self.ndb.interfaces[bridge]['index'])
         .commit())

        assert grep('%s ip link show' % self.ssh,
                    pattern=bridge)
        assert grep('%s ip link show' % self.ssh,
                    pattern='%s.*%s' % (brport, bridge))

    def test_vrf(self):
        vrf = self.ifname()
        (self
         .ndb
         .interfaces
         .add(ifname=vrf, kind='vrf')
         .set('vrf_table', 42)
         .commit())
        assert grep('%s ip link show' % self.ssh, pattern=vrf)

    def test_vlan(self):
        host = self.ifname()
        vlan = self.ifname()
        (self
         .ndb
         .interfaces
         .add(ifname=host, kind='dummy')
         .commit())
        (self
         .ndb
         .interfaces
         .add(ifname=vlan, kind='vlan')
         .set('link', self.ndb.interfaces[host]['index'])
         .set('vlan_id', 101)
         .commit())
        assert grep('%s ip link show' % self.ssh, pattern=vlan)

    def test_vxlan(self):
        host = self.ifname()
        vxlan = self.ifname()
        (self
         .ndb
         .interfaces
         .add(ifname=host, kind='dummy')
         .commit())
        (self
         .ndb
         .interfaces
         .add(ifname=vxlan, kind='vxlan')
         .set('vxlan_link', self.ndb.interfaces[host]['index'])
         .set('vxlan_id', 101)
         .set('vxlan_group', '239.1.1.1')
         .set('vxlan_ttl', 16)
         .commit())
        assert grep('%s ip link show' % self.ssh, pattern=vxlan)

    def test_basic_address(self):

        ifaddr = self.ifaddr()
        ifname = self.ifname()
        i = (self
             .ndb
             .interfaces
             .add(ifname=ifname, kind='dummy', state='up'))
        i.commit()

        a = (self
             .ndb
             .addresses
             .add(index=i['index'],
                  address=ifaddr,
                  prefixlen=24))
        a.commit()
        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)

    def test_basic_route(self):

        ifaddr = self.ifaddr()
        router = self.ifaddr()
        ifname = self.ifname()
        i = (self
             .ndb
             .interfaces
             .add(ifname=ifname, kind='dummy', state='up'))
        i.commit()

        a = (self
             .ndb
             .addresses
             .add(index=i['index'],
                  address=ifaddr,
                  prefixlen=24))
        a.commit()

        r = (self
             .ndb
             .routes
             .add(dst_len=24,
                  dst=str(self.ipnets[1].network),
                  gateway=router))
        r.commit()
        assert grep('%s ip link show' % self.ssh,
                    pattern=ifname)
        assert grep('%s ip addr show dev %s' % (self.ssh, ifname),
                    pattern=ifaddr)
        assert grep('%s ip route show' % self.ssh,
                    pattern='%s.*%s' % (str(self.ipnets[1]), ifname))


class TestRollback(TestBase):

    def setup(self):
        require_user('root')
        self.ipnets = [allocate_network() for _ in range(5)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.nl_kwarg['class'] = self.nl_class
        self.ndb = NDB(db_provider=self.db_provider,
                       db_spec=self.db_spec,
                       rtnl_log=True,
                       sources={'localhost': self.nl_kwarg})
        self.ndb.debug('../ndb-%s-%s.log' % (os.getpid(), id(self.ndb)))

    def test_simple_deps(self):

        # register NDB handler to wait for the interface
        self.if_simple = uifname()

        ifaddr = self.ifaddr()
        router = self.ifaddr()
        dst = str(self.ipnets[1].network)

        with self.nl_class(**self.nl_kwarg) as ipr:
            self.interfaces = []
            #
            # simple dummy interface with one address and
            # one dependent route
            #
            ipr.link('add',
                     ifname=self.if_simple,
                     kind='dummy')
            self.ndb.wait({'interfaces': [{'ifname': self.if_simple}]})
            (self
             .interfaces
             .append(self
                     .ndb
                     .interfaces[self.if_simple]['index']))
            ipr.link('set',
                     index=self.interfaces[-1],
                     state='up')
            ipr.addr('add',
                     index=self.interfaces[-1],
                     address=ifaddr,
                     prefixlen=24)
            ipr.route('add',
                      dst=dst,
                      dst_len=24,
                      gateway=router)

        self.ndb.wait({'addresses': [{'address': ifaddr}],
                       'routes': [{'dst': dst}]})
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

        with self.nl_class(**self.nl_kwarg) as ipr:
            self.interfaces = []
            ipr.link('add',
                     ifname=self.if_br0,
                     kind='bridge')
            ipr.link('add',
                     ifname=self.if_br0p0,
                     kind='dummy')
            ipr.link('add',
                     ifname=self.if_br0p1,
                     kind='dummy')
            self.ndb.wait({'interfaces': [{'ifname': self.if_br0},
                                          {'ifname': self.if_br0p0},
                                          {'ifname': self.if_br0p1}]})
            self.interfaces.append(self.ndb.interfaces[self.if_br0]['index'])
            self.interfaces.append(self.ndb.interfaces[self.if_br0p0]['index'])
            self.interfaces.append(self.ndb.interfaces[self.if_br0p1]['index'])
            ipr.link('set',
                     index=self.interfaces[-3],
                     state='up')
            ipr.addr('add',
                     index=self.interfaces[-3],
                     address=ifaddr1,
                     prefixlen=24)
            ipr.addr('add',
                     index=self.interfaces[-3],
                     address=ifaddr2,
                     prefixlen=24)
            ipr.route('add',
                      dst=dst,
                      dst_len=24,
                      gateway=router)
            ipr.link('set',
                     index=self.interfaces[-1],
                     state='up',
                     master=self.interfaces[-3])
            ipr.link('set',
                     index=self.interfaces[-2],
                     state='up',
                     master=self.interfaces[-3])

        master = self.ndb.interfaces[self.if_br0]['index']
        self.ndb.wait({'interfaces': [{'ifname': self.if_br0p0,
                                       'master': master},
                                      {'ifname': self.if_br0p1,
                                       'master': master}],
                       'addresses': [{'address': ifaddr1},
                                     {'address': ifaddr2}],
                       'routes': [{'dst': dst}]})
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

        with self.nl_class(**self.nl_kwarg) as ipr:
            self.interfaces = []
            ipr.link('add',
                     ifname=if_host,
                     kind='dummy')
            self.ndb.wait({'interfaces': [{'ifname': if_host}]})
            self.interfaces.append(self.ndb.interfaces[if_host]['index'])
            ipr.link('set',
                     index=self.interfaces[-1],
                     state='up')
            ipr.link('add',
                     ifname=if_vlan,
                     kind='vlan',
                     link=self.interfaces[-1],
                     vlan_id=1001)
            self.ndb.wait({'interfaces': [{'ifname': if_vlan}]})
            self.interfaces.append(self.ndb.interfaces[if_vlan]['index'])
            ipr.link('set',
                     index=self.interfaces[-1],
                     state='up')
            ipr.addr('add',
                     index=self.interfaces[-1],
                     address=ifaddr1,
                     prefixlen=24)
            ipr.addr('add',
                     index=self.interfaces[-1],
                     address=ifaddr2,
                     prefixlen=24)
            ipr.route('add',
                      dst=dst,
                      dst_len=24,
                      gateway=router)
            self.ndb.wait({'addresses': [{'address': ifaddr1},
                                         {'address': ifaddr2}],
                           'routes': [{'dst': dst}]})

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


class TestSchema(TestBase):

    def test_basic(self):
        assert len(set(self.interfaces) -
                   set([x[0] for x in
                        self.fetch('select f_index from interfaces')])) == 0

    def test_vlan_interfaces(self):
        assert len(self.fetch('select * from vlan')) >= 2

    def test_bridge_interfaces(self):
        assert len(self.fetch('select * from bridge')) >= 1


class TestSources(TestBase):

    def count_interfaces(self, target):
        with self.ndb.schema.db_lock:
            return (self
                    .ndb
                    .schema
                    .execute('''
                             SELECT count(*) FROM interfaces
                             WHERE f_target = '%s'
                             ''' % target)
                    .fetchone()[0])

    def test_connect_netns(self):
        nsname = str(uuid.uuid4())
        with self.ndb.schema.db_lock:
            s = len(self.ndb.interfaces.summary()) - 1
            assert self.count_interfaces(nsname) == 0
            assert self.count_interfaces('localhost') == s

        # connect RTNL source
        event = threading.Event()
        self.ndb.connect_source(nsname, NetNS(nsname), event)
        assert event.wait(5)

        with self.ndb.schema.db_lock:
            s = len(self.ndb.interfaces.summary()) - 1
            assert self.count_interfaces(nsname) > 0
            assert self.count_interfaces('localhost') < s

        # disconnect the source
        self.ndb.disconnect_source(nsname)
        with self.ndb.schema.db_lock:
            s = len(self.ndb.interfaces.summary()) - 1
            assert self.count_interfaces(nsname) == 0
            assert self.count_interfaces('localhost') == s

        netns.remove(nsname)

    def test_disconnect_localhost(self):
        with self.ndb.schema.db_lock:
            s = len(self.ndb.interfaces.summary()) - 1
            assert self.count_interfaces('localhost') == s

        self.ndb.disconnect_source('localhost')

        with self.ndb.schema.db_lock:
            s = len(self.ndb.interfaces.summary()) - 1
            assert self.count_interfaces('localhost') == s
            assert s == 0


class TestReports(TestBase):

    def test_types(self):
        report.MAX_REPORT_LINES = 1
        # check for the report type here
        assert isinstance(self.ndb.interfaces.summary(), Report)
        # repr must be a string
        assert isinstance(repr(self.ndb.interfaces.summary()), basestring)
        # header + MAX_REPORT_LINES + (...)
        assert len(repr(self.ndb.interfaces.summary()).split('\n')) == 3

    def test_dump(self):
        for record in self.ndb.addresses.dump():
            assert isinstance(record, tuple)

    def test_csv(self):
        record_length = 0

        for record in self.ndb.routes.dump():
            if record_length == 0:
                record_length = len(record)
            else:
                assert len(record) == record_length

        for record in self.ndb.routes.csv():
            assert len(record.split(',')) == record_length

    def test_nested_ipaddr(self):
        records = len(repr(self
                           .ndb
                           .interfaces[self.if_bridge]
                           .ipaddr
                           .summary()).split('\n'))
        # 2 ipaddr + header
        assert records == 3

    def test_nested_ports(self):
        records = len(repr(self
                           .ndb
                           .interfaces[self.if_bridge]
                           .ports
                           .summary()).split('\n'))
        # 1 port + header
        assert records == 2
