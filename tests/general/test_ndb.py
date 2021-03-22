import os
import uuid
from utils import grep
from utils import require_user
from utils import allocate_network
from utils import free_network
from pyroute2 import netns
from pyroute2 import NDB
from pyroute2 import IPRoute
from pyroute2.common import uifname


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


class TestSchema(TestPreSet):

    def test_basic(self):
        assert len(set(self.interfaces) -
                   set([x[0] for x in
                        self.fetch('select f_index from interfaces')])) == 0

    def _test_vlan_interfaces(self):
        assert len(tuple(self.fetch('select * from vlan'))) >= 2

    def _test_bridge_interfaces(self):
        assert len(tuple(self.fetch('select * from bridge'))) >= 1
