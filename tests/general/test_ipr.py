import os
import time
import uuid
import errno
import socket
from functools import partial
from pyroute2 import NetNS
from pyroute2 import IPRoute
from pyroute2 import NetlinkError
from pyroute2.common import uifname
from pyroute2.common import AF_MPLS
from pyroute2.netlink import nlmsg
from pyroute2.netlink.rtnl.req import IPRouteRequest
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifinfmsg import IFF_NOARP
from pyroute2.netlink.rtnl.rtmsg import RTNH_F_ONLINK
from utils import grep
from utils import require_user
from utils import require_python
from utils import require_kernel
from utils import get_ip_default_routes
from utils import get_ip_rules
from utils import remove_link
from utils import allocate_network
from utils import free_network
from utils import skip_if_not_supported
from nose.plugins.skip import SkipTest
from nose.tools import assert_raises


class TestSetup(object):

    def test_simple(self):
        ip = IPRoute()
        ip.close()

    def test_multiple_instances(self):
        ip1 = IPRoute()
        ip2 = IPRoute()
        ip1.close()
        ip2.close()

    def test_fileno_fail(self):
        require_python(2)
        try:
            IPRoute(fileno=13)
        except NotImplementedError:
            pass

    def test_close(self):
        ip = IPRoute()
        ip.get_links()
        ip.close()

        # Shouldn't be able to use the socket after closing
        with assert_raises(socket.error):
            ip.get_links()

    def test_fileno(self):
        require_python(3)
        ip1 = IPRoute()
        ip2 = IPRoute(fileno=ip1.fileno())

        ip2.bind()
        try:
            ip1.bind()
        except OSError as e:
            if e.errno != 22:  # bind -> Invalid argument
                raise

        ip1.close()
        try:
            ip2.get_links()
        except OSError as e:
            if e.errno != 9:   # sendto -> Bad file descriptor
                raise

        try:
            ip2.close()
        except OSError as e:
            if e.errno != 9:   # close -> Bad file descriptor
                raise


class TestMisc(object):

    def setup(self):
        self.ip = IPRoute()

    def teardown(self):
        self.ip.close()

    def test_get_policy_map(self):
        assert isinstance(self.ip.get_policy_map(), dict)

    def test_register_policy(self):
        self.ip.register_policy(100, nlmsg)
        self.ip.register_policy({101: nlmsg})
        self.ip.register_policy(102, nlmsg)

        assert self.ip.get_policy_map()[100] == nlmsg
        assert self.ip.get_policy_map(101)[101] == nlmsg
        assert self.ip.get_policy_map([102])[102] == nlmsg

        self.ip.unregister_policy(100)
        self.ip.unregister_policy([101])
        self.ip.unregister_policy({102: nlmsg})

        assert 100 not in self.ip.get_policy_map()
        assert 101 not in self.ip.get_policy_map()
        assert 102 not in self.ip.get_policy_map()

    def test_addrpool_expand(self):
        # see coverage
        for i in range(100):
            self.ip.get_addr()

    def test_nla_compare(self):
        lvalue = self.ip.get_links()
        rvalue = self.ip.get_links()
        assert lvalue is not rvalue
        if lvalue == rvalue:
            pass
        if lvalue != rvalue:
            pass
        assert lvalue != 42


def _callback(msg, obj):
    obj.cb_counter += 1


class TestIPRoute(object):

    ipnets = []
    ipranges = []
    ifnames = []

    def setup(self):
        self.ip = IPRoute()
        self.ipnets = [allocate_network() for _ in range(3)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.ifaces = []
        self.ifnames = []
        try:
            self.dev, idx = self.create()
        except IndexError:
            pass

    def create(self, kind='dummy'):
        require_user('root')
        name = uifname()
        self.ip.link('add', ifname=name, kind=kind)
        idx = None
        while not idx:
            idx = self.ip.link_lookup(ifname=name)
        idx = idx[0]
        self.ifaces.append(idx)
        return (name, idx)

    def uifname(self):
        ifname = uifname()
        self.ifnames.append(ifname)
        return ifname

    def teardown(self):
        for net in self.ipnets:
            free_network(net)
        if hasattr(self, 'ifaces'):
            for dev in reversed(self.ifaces):
                try:
                    self.ip.link('delete', index=dev)
                except:
                    pass
        for name in reversed(self.ifnames):
            try:
                (self
                 .ip
                 .link('del', index=(self
                                     .ip
                                     .link_lookup(ifname=name)[0])))
            except:
                pass
        self.ip.close()

    def ifaddr(self, r=0):
        return str(self.ipranges[r].pop())

    def test_brport_basic(self):
        require_user('root')
        (bn, bx) = self.create('bridge')
        (sn, sx) = self.create('dummy')
        self.ip.link('set', index=sx, master=bx)
        self.ip.link('set', index=sx, state='up')
        self.ip.link('set', index=bx, state='up')

        self.ip.brport('set',
                       index=sx,
                       unicast_flood=0,
                       cost=200,
                       proxyarp=1)

        port = self.ip.brport('show', index=sx)[0]
        protinfo = port.get_attr('IFLA_PROTINFO')
        assert protinfo.get_attr('IFLA_BRPORT_COST') == 200
        assert protinfo.get_attr('IFLA_BRPORT_PROXYARP') == 1
        assert protinfo.get_attr('IFLA_BRPORT_UNICAST_FLOOD') == 0

    def test_match_callable(self):
        assert len(self.ip.get_links(match=partial(lambda x: x))) > 0


    def test_get_netns_info(self):
        require_user('root')
        nsname = str(uuid.uuid4())
        netns = NetNS(nsname)
        try:
            peer = {'ifname': self.uifname(),
                    'net_ns_fd': nsname}
            ifname = self._create_veth(peer)
            # get veth
            veth = self.ip.link('get', ifname=ifname)[0]
            target = veth.get_attr('IFLA_LINK_NETNSID')
            for info in self.ip.get_netns_info():
                path = info.get_attr('NSINFO_PATH')
                assert path.endswith(nsname)
                netnsid = info['netnsid']
                if target == netnsid:
                    break
            else:
                raise KeyError('peer netns not found')
        finally:
            netns.close()
            netns.remove()


    def _test_ntables(self):
        setA = set(filter(lambda x: x is not None,
                          [x.get_attr('NDTA_PARMS').get_attr('NDTPA_IFINDEX')
                           for x in self.ip.get_ntables()]))
        setB = set([x['index'] for x in self.ip.get_links()])
        assert setA == setB

    def test_fdb_vxlan(self):
        require_kernel(4, 4)
        require_user('root')
        ifaddr = self.ifaddr()
        # create dummy
        (dn, dx) = self._create('dummy')
        # create vxlan on it
        (vn, vx) = self._create('vxlan', vxlan_link=dx, vxlan_id=500)
        # create FDB record
        l2 = '00:11:22:33:44:55'
        self.ip.fdb('add', lladdr=l2, ifindex=vx,
                    vni=600, port=5678, dst=ifaddr)
        # dump
        r = self.ip.fdb('dump', ifindex=vx, lladdr=l2)
        assert len(r) == 1
        assert r[0]['ifindex'] == vx
        assert r[0].get_attr('NDA_LLADDR') == l2
        assert r[0].get_attr('NDA_DST') == ifaddr
        assert r[0].get_attr('NDA_PORT') == 5678
        assert r[0].get_attr('NDA_VNI') == 600

    def test_fdb_bridge_simple(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 4)
        try:
            self.test_vlan_filter_add()
        except SkipTest:
            raise
        # create bridge
        (bn, bx) = self._create('bridge')
        # create FDB record
        l2 = '00:11:22:33:44:55'
        self.ip.fdb('add', lladdr=l2, ifindex=bx)
        # dump FDB
        r = self.ip.fdb('dump', ifindex=bx, lladdr=l2)
        # one vlan == 1, one w/o vlan
        assert len(r) == 2
        assert len(list(filter(lambda x: x['ifindex'] == bx, r))) == 2
        assert len(list(filter(lambda x: x.get_attr('NDA_VLAN'), r))) == 1
        assert len(list(filter(lambda x: x.get_attr('NDA_MASTER') == bx,
                               r))) == 2
        assert len(list(filter(lambda x: x.get_attr('NDA_LLADDR') == l2,
                               r))) == 2
        r = self.ip.fdb('dump', ifindex=bx, lladdr=l2, vlan=1)
        assert len(r) == 1
        assert r[0].get_attr('NDA_VLAN') == 1
        assert r[0].get_attr('NDA_MASTER') == bx
        assert r[0].get_attr('NDA_LLADDR') == l2

    def test_neigh_real_links(self):
        links = set([x['index'] for x in self.ip.get_links()])
        neigh = set([x['ifindex'] for x in self.ip.get_neighbours()])
        assert neigh < links

    def test_neigh_filter(self):
        require_user('root')
        ifaddr1 = self.ifaddr(1)
        ifaddr2 = self.ifaddr(1)
        # inject arp records
        self.ip.neigh('add',
                      dst=ifaddr1,
                      lladdr='00:11:22:33:44:55',
                      ifindex=self.ifaces[0])
        self.ip.neigh('add',
                      dst=ifaddr2,
                      lladdr='00:11:22:33:44:55',
                      ifindex=self.ifaces[0])
        # assert two arp records on the interface
        assert len(self.ip.get_neighbours(ifindex=self.ifaces[0])) == 2
        # filter by dst
        assert len(self.ip.get_neighbours(dst=ifaddr1)) == 1
        # filter with lambda
        assert len(self.ip.get_neighbours(match=lambda x: x['ifindex'] ==
                                          self.ifaces[0])) == 2

    def test_neigh_get(self):
        require_user('root')
        ifaddr1 = self.ifaddr(1)
        self.ip.neigh('add',
                      dst=ifaddr1,
                      lladdr='00:11:22:33:44:55',
                      ifindex=self.ifaces[0])
        res = self.ip.neigh('get',
                            dst=ifaddr1,
                            ifindex=self.ifaces[0])
        assert res[0].get_attr("NDA_DST") == ifaddr1

    def test_mass_ipv6(self):
        #
        # Achtung! This test is time consuming.
        # It is really time consuming, I'm not not
        # kidding you. Beware.
        #
        require_user('root')
        ipv6net = allocate_network('ipv6')
        base = str(ipv6net.network) + '{0}'
        limit = int(os.environ.get('PYROUTE2_SLIMIT', '0x800'), 16)

        # add addresses
        for idx in range(limit):
            self.ip.addr('add', self.ifaces[0],
                         base.format(hex(idx)[2:]), 48)

        # assert addresses in two steps, to ease debug
        addrs = self.ip.get_addr(10)
        assert len(addrs) >= limit

        # clean up addresses
        #
        # it is not required, but if you don't do that,
        # you'll get this on the interface removal:
        #
        # >> kernel:BUG: soft lockup - CPU#0 stuck for ...
        #
        # so, not to scare people, remove addresses gracefully
        # one by one
        #
        # it also verifies all the addresses are in place
        for idx in reversed(range(limit)):
            self.ip.addr('delete', self.ifaces[0],
                         base.format(hex(idx)[2:]), 48)

        free_network(ipv6net, 'ipv6')

    def test_fail_not_permitted(self):
        ifaddr = self.ifaddr()
        try:
            self.ip.addr('add', 1, address=ifaddr, mask=24)
        except NetlinkError as e:
            if e.code != errno.EPERM:  # Operation not permitted
                raise
        finally:
            try:
                self.ip.addr('delete', 1, address=ifaddr, mask=24)
            except:
                pass

    def test_symbolic_flags_ifaddrmsg(self):
        require_user('root')
        ifaddr = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], ifaddr, 24)
        addr = [x for x in self.ip.get_addr()
                if x.get_attr('IFA_LOCAL') == ifaddr][0]
        assert 'IFA_F_PERMANENT' in addr.flags2names(addr['flags'])

    def test_callbacks_positive(self):
        require_user('root')
        dev = self.ifaces[0]

        self.cb_counter = 0
        self.ip.register_callback(_callback,
                                  lambda x: x.get('index', None) == dev,
                                  (self, ))
        self.test_updown_link()
        assert self.cb_counter > 0
        self.ip.unregister_callback(_callback)

    def test_callbacks_negative(self):
        require_user('root')

        self.cb_counter = 0
        self.ip.register_callback(_callback,
                                  lambda x: x.get('index', None) == -1,
                                  (self, ))
        self.test_updown_link()
        assert self.cb_counter == 0
        self.ip.unregister_callback(_callback)
