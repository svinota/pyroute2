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
from utils import get_ip_brd
from utils import get_ip_addr
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

    def _test_nla_operators(self):
        require_user('root')
        self.ip.addr('add', self.ifaces[0], address='172.16.0.1', mask=24)
        self.ip.addr('add', self.ifaces[0], address='172.16.0.2', mask=24)
        r = [x for x in self.ip.get_addr() if x['index'] == self.ifaces[0]]
        complement = r[0] - r[1]
        intersection = r[0] & r[1]

        assert complement.get_attr('IFA_ADDRESS') == '172.16.0.1'
        assert complement.get_attr('IFA_LABEL') is None
        assert complement['prefixlen'] == 0
        assert complement['index'] == 0

        assert intersection.get_attr('IFA_ADDRESS') is None
        assert intersection.get_attr('IFA_LABEL') == self.dev
        assert intersection['prefixlen'] == 24
        assert intersection['index'] == self.ifaces[0]

    def test_addr_add(self):
        require_user('root')
        ifaddr = self.ifaddr()
        self.ip.addr('add', self.ifaces[0], address=ifaddr, mask=24)
        assert '{0}/24'.format(ifaddr) in get_ip_addr()

    def test_addr_replace(self):
        require_user('root')
        ifaddr = self.ifaddr()
        self.ip.addr('replace', self.ifaces[0], address=ifaddr, mask=24)
        assert '{0}/24'.format(ifaddr) in get_ip_addr()
        self.ip.addr('replace', self.ifaces[0], address=ifaddr, mask=24)

    def test_vlan_filter_dump(self):
        require_user('root')
        (an, ax) = self.create('bridge')
        (bn, bx) = self.create('bridge')
        self.ip.link('set', index=ax, state='up')
        self.ip.link('set', index=bx, state='up')
        assert len(self.ip.get_vlans()) >= 2
        for name in (an, bn):
            assert len(self.ip.get_vlans(ifname=name)) == 1
            assert (self
                    .ip
                    .get_vlans(ifname=name)[0]
                    .get_attr('IFLA_IFNAME')) == name
            assert (self
                    .ip
                    .get_vlans(ifname=name)[0]
                    .get_nested('IFLA_AF_SPEC',
                                'IFLA_BRIDGE_VLAN_INFO'))['vid'] == 1

    def test_vlan_filter_add(self):
        require_user('root')
        (bn, bx) = self.create('bridge')
        (sn, sx) = self.create('dummy')
        self.ip.link('set', index=sx, master=bx)
        assert not grep('bridge vlan show', pattern=' 568')
        self.ip.vlan_filter('add', index=sx, vlan_info={'vid': 568})
        assert grep('bridge vlan show', pattern=' 568')
        self.ip.vlan_filter('del', index=sx, vlan_info={'vid': 568})
        assert not grep('bridge vlan show', pattern=' 568')

    def test_vlan_filter_add_raw(self):
        require_user('root')
        (bn, bx) = self.create('bridge')
        (sn, sx) = self.create('dummy')
        self.ip.link('set', index=sx, master=bx)
        assert not grep('bridge vlan show', pattern=' 567')
        self.ip.vlan_filter('add', index=sx,
                            af_spec={'attrs': [['IFLA_BRIDGE_VLAN_INFO',
                                                {'vid': 567}]]})
        assert grep('bridge vlan show', pattern=' 567')
        self.ip.vlan_filter('del', index=sx,
                            af_spec={'attrs': [['IFLA_BRIDGE_VLAN_INFO',
                                                {'vid': 567}]]})
        assert not grep('bridge vlan show', pattern=' 567')

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

    def test_local_add(self):
        require_user('root')
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.addr('add', self.ifaces[0],
                     address=ifaddr1,
                     local=ifaddr2,
                     mask=24)
        link = self.ip.get_addr(index=self.ifaces[0])[0]
        address = link.get_attr('IFA_ADDRESS')
        local = link.get_attr('IFA_LOCAL')
        assert address == ifaddr1
        assert local == ifaddr2

    def test_addr_broadcast(self):
        require_user('root')
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.addr('add', self.ifaces[0],
                     address=ifaddr1,
                     mask=24,
                     broadcast=ifaddr2)
        assert ifaddr2 in get_ip_brd()

    def test_addr_broadcast_default(self):
        require_user('root')
        ifaddr1 = self.ifaddr()  # -> 255
        ifaddr2 = self.ifaddr()  # -> 254
        self.ip.addr('add', self.ifaces[0],
                     address=ifaddr2,
                     mask=24,
                     broadcast=True)
        assert ifaddr1 in get_ip_brd()

    def test_flush_addr(self):
        require_user('root')
        ifaddr1 = self.ifaddr(0)
        ifaddr2 = self.ifaddr(0)
        ifaddr3 = self.ifaddr(1)
        ifaddr4 = self.ifaddr(1)
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        self.ip.addr('add', self.ifaces[0], address=ifaddr2, mask=24)
        self.ip.addr('add', self.ifaces[0], address=ifaddr3, mask=24)
        self.ip.addr('add', self.ifaces[0], address=ifaddr4, mask=24)
        assert len(self.ip.get_addr(index=self.ifaces[0],
                                    family=socket.AF_INET)) == 4
        self.ip.flush_addr(index=self.ifaces[0])
        assert len(self.ip.get_addr(index=self.ifaces[0],
                                    family=socket.AF_INET)) == 0

    def test_flush_rules(self):
        require_user('root')
        ifaddr1 = self.ifaddr(0)
        ifaddr2 = self.ifaddr(1)
        init = len(self.ip.get_rules(family=socket.AF_INET))
        assert len(self.ip.get_rules(priority=lambda x: 100 < x < 500)) == 0
        self.ip.rule('add', table=10, priority=110)
        self.ip.rule('add', table=15, priority=150, action='FR_ACT_PROHIBIT')
        self.ip.rule('add', table=20, priority=200, src=ifaddr1)
        self.ip.rule('add', table=25, priority=250, dst=ifaddr2)
        assert len(self.ip.get_rules(priority=lambda x: 100 < x < 500)) == 4
        assert len(self.ip.get_rules(src=ifaddr1)) == 1
        assert len(self.ip.get_rules(dst=ifaddr2)) == 1
        self.ip.flush_rules(family=socket.AF_INET,
                            priority=lambda x: 100 < x < 500)
        assert len(self.ip.get_rules(priority=lambda x: 100 < x < 500)) == 0
        assert len(self.ip.get_rules(src=ifaddr1)) == 0
        assert len(self.ip.get_rules(dst=ifaddr2)) == 0
        assert len(self.ip.get_rules(family=socket.AF_INET)) == init

    def test_rules_deprecated(self):
        require_user('root')
        init = len(self.ip.get_rules(family=socket.AF_INET))
        assert len(self.ip.get_rules(priority=lambda x: 100 < x < 500)) == 0
        self.ip.rule('add', 10, 110)
        self.ip.rule('add', 15, 150, 'FR_ACT_PROHIBIT')
        assert len(self.ip.get_rules(priority=lambda x: 100 < x < 500)) == 2
        self.ip.flush_rules(family=socket.AF_INET,
                            priority=lambda x: 100 < x < 500)
        assert len(self.ip.get_rules(priority=lambda x: 100 < x < 500)) == 0
        assert len(self.ip.get_rules(family=socket.AF_INET)) == init

    def test_match_callable(self):
        assert len(self.ip.get_links(match=partial(lambda x: x))) > 0

    def test_addr_filter(self):
        require_user('root')
        ifaddr_brd = self.ifaddr()
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.addr('add',
                     index=self.ifaces[0],
                     address=ifaddr1,
                     prefixlen=24,
                     broadcast=ifaddr_brd)
        self.ip.addr('add',
                     index=self.ifaces[0],
                     address=ifaddr2,
                     prefixlen=24,
                     broadcast=ifaddr_brd)
        assert len(self.ip.get_addr(index=self.ifaces[0])) == 2
        assert len(self.ip.get_addr(address=ifaddr1)) == 1
        assert len(self.ip.get_addr(broadcast=ifaddr_brd)) == 2
        assert len(self.ip.get_addr(match=lambda x: x['index'] ==
                                    self.ifaces[0])) == 2

    @skip_if_not_supported
    def _create_ipvlan(self, smode):
        require_user('root')
        master = self.uifname()
        ipvlan = self.uifname()
        # create the master link
        self.ip.link('add', ifname=master, kind='dummy')
        midx = self.ip.link_lookup(ifname=master)[0]
        # check modes
        # maybe move modes dict somewhere else?
        cmode = ifinfmsg.ifinfo.data_map['ipvlan'].modes[smode]
        assert ifinfmsg.ifinfo.data_map['ipvlan'].modes[cmode] == smode
        # create ipvlan
        self.ip.link('add',
                     ifname=ipvlan,
                     kind='ipvlan',
                     link=midx,
                     mode=cmode)
        devs = self.ip.link_lookup(ifname=ipvlan)
        assert devs

    def test_create_ipvlan_l2(self):
        return self._create_ipvlan('IPVLAN_MODE_L2')

    def test_create_ipvlan_l3(self):
        return self._create_ipvlan('IPVLAN_MODE_L3')

    def _create_veth(self, peer):
        ifname = self.uifname()
        self.ip.link('add', kind='veth', ifname=ifname, peer=peer)
        assert len(self.ip.link_lookup(ifname=ifname)) > 0
        return ifname

    def test_create_veth_simple(self):
        require_user('root')
        peer = self.uifname()
        self._create_veth(peer)
        assert len(self.ip.link_lookup(ifname=peer)) > 0

    def test_create_veth_attrs(self):
        require_user('root')
        nsname = str(uuid.uuid4())
        netns = NetNS(nsname)
        try:
            peer = {'ifname': self.uifname(),
                    'net_ns_fd': nsname}
            self._create_veth(peer)
            assert len(self.ip.link_lookup(ifname=peer['ifname'])) == 0
            assert len(netns.link_lookup(ifname=peer['ifname'])) > 0
        finally:
            netns.close()
            netns.remove()

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

    @skip_if_not_supported
    def _create(self, kind, **kwarg):
        name = self.uifname()
        self.ip.link('add', ifname=name, kind=kind, **kwarg)
        devs = self.ip.link_lookup(ifname=name)
        assert devs
        return (name, devs[0])

    def test_create_dummy(self):
        require_user('root')
        self._create('dummy')

    def test_create_bond(self):
        require_user('root')
        self._create('bond')

    def test_create_bridge(self):
        require_user('root')
        self._create('bridge')

    def test_create_team(self):
        require_user('root')
        self._create('team')

    def test_create_vti(self):
        require_user('root')
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        (ifname, idx) = self.create()
        self.ip.link('set', index=idx, state='up')
        self.ip.addr('add', index=idx, address=ifaddr1, mask=24)
        self._create('vti',
                     vti_link=idx,
                     vti_local=ifaddr1,
                     vti_remote=ifaddr2,
                     vti_ikey=64,
                     vti_okey=72)

    def test_create_vti6(self):
        require_user('root')
        self._create('vti6',
                     vti_link=2,
                     vti_local='fd00:1:2:3:4:1::1',
                     vti_remote='fd00:1:2:3:4:2::1',
                     vti_ikey=80,
                     vti_okey=88)

    def test_create_xfrm(self):
        require_user('root')
        # XXX: Currently does not work on top of a dummy device
        idx = self.ip.link_lookup(ifname='lo')[0]
        # # Create Dummy for Parent
        # (_, idx) = self.create()
        self.ip.link('set', index=idx, state='up')
        # Create XFRM Interface on It
        self._create('xfrm',
                     xfrm_link=idx,
                     xfrm_if_id=555)

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

    def test_fail_no_such_device(self):
        require_user('root')
        ifaddr = self.ifaddr()
        dev = sorted([i['index'] for i in self.ip.get_links()])[-1] + 10
        try:
            self.ip.addr('add',
                         dev,
                         address=ifaddr,
                         mask=24)
        except NetlinkError as e:
            if e.code != errno.ENODEV:  # No such device
                raise

    def test_remove_link(self):
        require_user('root')
        try:
            self.ip.link('del', index=self.ifaces[0])
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname=self.dev)) == 0

    def _test_route_proto(self, proto, fake, spec=''):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        os.system('ip route add %s/24 via 127.0.0.1 %s' % (naddr, spec))

        time.sleep(1)

        assert grep('ip ro', pattern='%s/24.*127.0.0.1' % naddr)
        try:
            self.ip.route('del',
                          dst='%s/24' % naddr,
                          gateway='127.0.0.1',
                          proto=fake)
        except NetlinkError:
            pass
        self.ip.route('del',
                      dst='%s/24' % naddr,
                      gateway='127.0.0.1',
                      proto=proto)
        assert not grep('ip ro', pattern='%s/24.*127.0.0.1' % naddr)

    def test_route_proto_static(self):
        return self._test_route_proto('static', 'boot', 'proto static')

    def test_route_proto_static_num(self):
        return self._test_route_proto(4, 3, 'proto static')

    def test_route_proto_boot(self):
        return self._test_route_proto('boot', 4)

    def test_route_proto_boot_num(self):
        return self._test_route_proto(3, 'static')

    def test_route_oif_as_iterable(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        spec = {'dst': naddr,
                'dst_len': 24,
                'oif': (1, )}
        self.ip.route('add', **spec)
        rts = self.ip.get_routes(family=socket.AF_INET,
                                 dst=naddr)
        self.ip.route('del', **spec)
        assert len(rts) == 1
        assert rts[0].get_attr('RTA_OIF') == 1

    def test_route_get_target(self):
        if not self.ip.get_default_routes(table=254):
            raise SkipTest('no default IPv4 routes')
        rts = self.ip.get_routes(family=socket.AF_INET,
                                 dst='8.8.8.8',
                                 table=254)
        assert len(rts) > 0

    def test_route_get_target_default_ipv4(self):
        rts = self.ip.get_routes(dst='127.0.0.1')
        assert len(rts) > 0

    def test_route_get_target_default_ipv6(self):
        rts = self.ip.get_routes(dst='::1')
        assert len(rts) > 0

    def test_route_get_by_spec(self):
        require_user('root')
        ifaddr1 = self.ifaddr(0)
        ifaddr2 = self.ifaddr(1)
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', index=self.ifaces[0],
                     address=ifaddr1, mask=24)
        self.ip.addr('add', index=self.ifaces[0],
                     address=ifaddr2, mask=24)
        rts = self.ip.get_routes(family=socket.AF_INET,
                                 dst=lambda x: x in (ifaddr1,
                                                     ifaddr2))
        assert len(rts) == 4

    @skip_if_not_supported
    def _test_route_mpls_via_ipv(self, family, address, label):
        require_kernel(4, 4)
        require_user('root')
        self.ip.route('add', **{'family': AF_MPLS,
                                'oif': self.ifaces[0],
                                'via': {'family': family,
                                        'addr': address},
                                'newdst': {'label': label,
                                           'bos': 1}})
        rt = self.ip.get_routes(oif=self.ifaces[0], family=AF_MPLS)[0]
        assert rt.get_attr('RTA_VIA')['addr'] == address
        assert rt.get_attr('RTA_VIA')['family'] == family
        assert rt.get_attr('RTA_NEWDST')[0]['label'] == label
        assert len(rt.get_attr('RTA_NEWDST')) == 1
        self.ip.route('del', **{'family': AF_MPLS,
                                'oif': self.ifaces[0],
                                'dst': {'label': 0x10,
                                        'bos': 1},
                                'via': {'family': family,
                                        'addr': address},
                                'newdst': {'label': label,
                                           'bos': 1}})
        assert len(self.ip.get_routes(oif=self.ifaces[0], family=AF_MPLS)) == 0

    def test_route_mpls_via_ipv4(self):
        ifaddr = self.ifaddr()
        self._test_route_mpls_via_ipv(socket.AF_INET,
                                      ifaddr, 0x20)

    def test_route_mpls_via_ipv6(self):
        ipv6net = allocate_network('ipv6')
        address = str(ipv6net.network) + '7c32'
        self._test_route_mpls_via_ipv(socket.AF_INET6, address, 0x20)
        free_network(ipv6net, 'ipv6')

    @skip_if_not_supported
    def test_route_mpls_swap_newdst_simple(self):
        require_kernel(4, 4)
        require_user('root')
        req = {'family': AF_MPLS,
               'oif': self.ifaces[0],
               'dst': {'label': 0x20,
                       'bos': 1},
               'newdst': {'label': 0x21,
                          'bos': 1}}
        self.ip.route('add', **req)
        rt = self.ip.get_routes(oif=self.ifaces[0], family=AF_MPLS)[0]
        assert rt.get_attr('RTA_DST')[0]['label'] == 0x20
        assert len(rt.get_attr('RTA_DST')) == 1
        assert rt.get_attr('RTA_NEWDST')[0]['label'] == 0x21
        assert len(rt.get_attr('RTA_NEWDST')) == 1
        self.ip.route('del', **req)
        assert len(self.ip.get_routes(oif=self.ifaces[0], family=AF_MPLS)) == 0

    @skip_if_not_supported
    def test_route_mpls_swap_newdst_list(self):
        require_kernel(4, 4)
        require_user('root')
        req = {'family': AF_MPLS,
               'oif': self.ifaces[0],
               'dst': {'label': 0x20,
                       'bos': 1},
               'newdst': [{'label': 0x21,
                           'bos': 1}]}
        self.ip.route('add', **req)
        rt = self.ip.get_routes(oif=self.ifaces[0], family=AF_MPLS)[0]
        assert rt.get_attr('RTA_DST')[0]['label'] == 0x20
        assert len(rt.get_attr('RTA_DST')) == 1
        assert rt.get_attr('RTA_NEWDST')[0]['label'] == 0x21
        assert len(rt.get_attr('RTA_NEWDST')) == 1
        self.ip.route('del', **req)
        assert len(self.ip.get_routes(oif=self.ifaces[0], family=AF_MPLS)) == 0

    def test_route_multipath_raw(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst=naddr,
                      mask=24,
                      multipath=[{'hops': 20,
                                  'oif': 1,
                                  'attrs': [['RTA_GATEWAY', '127.0.0.2']]},
                                 {'hops': 30,
                                  'oif': 1,
                                  'attrs': [['RTA_GATEWAY', '127.0.0.3']]}])
        assert grep('ip route show', pattern='%s/24' % naddr)
        assert grep('ip route show', pattern='nexthop.*127.0.0.2.*weight 21')
        assert grep('ip route show', pattern='nexthop.*127.0.0.3.*weight 31')
        self.ip.route('del', dst=naddr, mask=24)

    def test_route_multipath_helper(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        req = IPRouteRequest({'dst': '%s/24' % naddr,
                              'multipath': [{'hops': 20,
                                             'oif': 1,
                                             'gateway': '127.0.0.2'},
                                            {'hops': 30,
                                             'oif': 1,
                                             'gateway': '127.0.0.3'}]})
        self.ip.route('add', **req)
        assert grep('ip route show', pattern='%s/24' % naddr)
        assert grep('ip route show', pattern='nexthop.*127.0.0.2.*weight 21')
        assert grep('ip route show', pattern='nexthop.*127.0.0.3.*weight 31')
        self.ip.route('del', dst=naddr, mask=24)

    def test_route_multipath(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      multipath=[{'gateway': '127.0.0.2'},
                                 {'gateway': '127.0.0.3'}])
        assert grep('ip route show', pattern='%s/24' % naddr)
        assert grep('ip route show', pattern='nexthop.*127.0.0.2')
        assert grep('ip route show', pattern='nexthop.*127.0.0.3')
        self.ip.route('del', dst=naddr, mask=24)

    def test_route_onlink(self):
        naddr = str(self.ipnets[1].network)
        ifaddr = self.ifaddr(0)
        require_user('root')
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      gateway=ifaddr,
                      oif=1,
                      flags=RTNH_F_ONLINK)
        assert grep('ip route show', pattern='%s.*onlink' % ifaddr)
        self.ip.route('del', dst='%s/24' % naddr)

    def test_route_onlink_multipath(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      multipath=[{'gateway': ifaddr1,
                                  'oif': 1,
                                  'flags': RTNH_F_ONLINK},
                                 {'gateway': ifaddr2,
                                  'oif': 1,
                                  'flags': RTNH_F_ONLINK}])
        assert grep('ip route show', pattern='%s/24' % naddr)
        assert grep('ip route show', pattern='nexthop.*%s.*onlink' % ifaddr1)
        assert grep('ip route show', pattern='nexthop.*%s.*onlink' % ifaddr2)
        self.ip.route('del', dst=naddr, mask=24)

    def test_route_onlink_strflags(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr = self.ifaddr()
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      gateway=ifaddr,
                      oif=1,
                      flags=['onlink'])
        assert grep('ip route show', pattern='%s.*onlink' % ifaddr)
        self.ip.route('del', dst='%s/24' % naddr)

    def test_route_onlink_multipath_strflags(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      multipath=[{'gateway': ifaddr1,
                                  'oif': 1,
                                  'flags': ['onlink']},
                                 {'gateway': ifaddr2,
                                  'oif': 1,
                                  'flags': RTNH_F_ONLINK}])
        assert grep('ip route show', pattern='%s/24' % naddr)
        assert grep('ip route show', pattern='nexthop.*%s.*onlink' % ifaddr1)
        assert grep('ip route show', pattern='nexthop.*%s.*onlink' % ifaddr2)
        self.ip.route('del', dst=naddr, mask=24)

    @skip_if_not_supported
    def test_lwtunnel_multipath_mpls(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 5)
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      multipath=[{'encap': {'type': 'mpls',
                                            'labels': 500},
                                  'oif': 1},
                                 {'encap': {'type': 'mpls',
                                            'labels': '600/700'},
                                  'gateway': '127.0.0.4'}])
        routes = self.ip.route('dump', dst='%s/24' % naddr)
        assert len(routes) == 1
        mp = routes[0].get_attr('RTA_MULTIPATH')
        assert len(mp) == 2
        assert mp[0]['oif'] == 1
        assert mp[0].get_attr('RTA_ENCAP_TYPE') == 1
        labels = mp[0].get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 1
        assert labels[0]['bos'] == 1
        assert labels[0]['label'] == 500
        assert mp[1].get_attr('RTA_ENCAP_TYPE') == 1
        labels = mp[1].get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 2
        assert labels[0]['bos'] == 0
        assert labels[0]['label'] == 600
        assert labels[1]['bos'] == 1
        assert labels[1]['label'] == 700
        self.ip.route('del', dst='%s/24' % naddr)

    @skip_if_not_supported
    def test_lwtunnel_mpls_dict_label(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 3)
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      encap={'type': 'mpls',
                             'labels': [{'bos': 0, 'label': 226},
                                        {'bos': 1, 'label': 227}]},
                      gateway='127.0.0.2')
        routes = self.ip.route('dump', dst='%s/24' % naddr)
        assert len(routes) == 1
        route = routes[0]
        assert route.get_attr('RTA_ENCAP_TYPE') == 1
        assert route.get_attr('RTA_GATEWAY') == '127.0.0.2'
        labels = route.get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 2
        assert labels[0]['bos'] == 0
        assert labels[0]['label'] == 226
        assert labels[1]['bos'] == 1
        assert labels[1]['label'] == 227
        self.ip.route('del', dst='%s/24' % naddr)

    @skip_if_not_supported
    def test_lwtunnel_mpls_2_int_label(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 3)
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      encap={'type': 'mpls',
                             'labels': [206, 207]},
                      oif=1)
        routes = self.ip.route('dump', dst='%s/24' % naddr)
        assert len(routes) == 1
        route = routes[0]
        assert route.get_attr('RTA_ENCAP_TYPE') == 1
        assert route.get_attr('RTA_OIF') == 1
        labels = route.get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 2
        assert labels[0]['bos'] == 0
        assert labels[0]['label'] == 206
        assert labels[1]['bos'] == 1
        assert labels[1]['label'] == 207
        self.ip.route('del', dst='%s/24' % naddr)

    @skip_if_not_supported
    def test_lwtunnel_mpls_2_str_label(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 3)
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      encap={'type': 'mpls',
                             'labels': "246/247"},
                      oif=1)
        routes = self.ip.route('dump', dst='%s/24' % naddr)
        assert len(routes) == 1
        route = routes[0]
        assert route.get_attr('RTA_ENCAP_TYPE') == 1
        assert route.get_attr('RTA_OIF') == 1
        labels = route.get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 2
        assert labels[0]['bos'] == 0
        assert labels[0]['label'] == 246
        assert labels[1]['bos'] == 1
        assert labels[1]['label'] == 247
        self.ip.route('del', dst='%s/24' % naddr)

    @skip_if_not_supported
    def test_lwtunnel_mpls_1_str_label(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 3)
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      encap={'type': 'mpls',
                             'labels': "244"},
                      oif=1)
        routes = self.ip.route('dump', dst='%s/24' % naddr)
        assert len(routes) == 1
        route = routes[0]
        assert route.get_attr('RTA_ENCAP_TYPE') == 1
        assert route.get_attr('RTA_OIF') == 1
        labels = route.get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 1
        assert labels[0]['bos'] == 1
        assert labels[0]['label'] == 244
        self.ip.route('del', dst='%s/24' % naddr)

    @skip_if_not_supported
    def test_lwtunnel_mpls_1_int_label(self):
        require_kernel(4, 4)
        require_user('root')
        require_kernel(4, 3)
        naddr = str(self.ipnets[1].network)
        self.ip.route('add',
                      dst='%s/24' % naddr,
                      encap={'type': 'mpls',
                             'labels': 245},
                      oif=1)
        routes = self.ip.route('dump', dst='%s/24' % naddr)
        assert len(routes) == 1
        route = routes[0]
        assert route.get_attr('RTA_ENCAP_TYPE') == 1
        assert route.get_attr('RTA_OIF') == 1
        labels = route.get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
        assert len(labels) == 1
        assert labels[0]['bos'] == 1
        assert labels[0]['label'] == 245
        self.ip.route('del', dst='%s/24' % naddr)

    def test_route_change_existing(self):
        # route('replace', ...) should succeed, if route exists
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        ifaddr3 = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        self.ip.route('add',
                      dst=naddr,
                      mask=24,
                      gateway=ifaddr2,
                      table=100)
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr, ifaddr2))
        self.ip.route('change',
                      dst=naddr,
                      mask=24,
                      gateway=ifaddr3,
                      table=100)
        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr, ifaddr2))
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr, ifaddr3))
        self.ip.flush_routes(table=100)
        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr, ifaddr3))

    def test_route_change_not_existing_fail(self):
        # route('change', ...) should fail, if no route exists
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        assert not grep('ip route show table 100',
                        pattern='%s.*%s' % (naddr, ifaddr2))
        try:
            self.ip.route('change',
                          dst=naddr,
                          mask=24,
                          gateway=ifaddr2,
                          table=100)
        except NetlinkError as e:
            if e.code != errno.ENOENT:
                raise

    def test_route_replace_existing(self):
        # route('replace', ...) should succeed, if route exists
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        ifaddr3 = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        self.ip.route('replace',
                      dst=naddr,
                      mask=24,
                      gateway=ifaddr2,
                      table=100)
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr, ifaddr2))
        self.ip.route('replace',
                      dst=naddr,
                      mask=24,
                      gateway=ifaddr3,
                      table=100)
        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr, ifaddr2))
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr, ifaddr3))
        self.ip.flush_routes(table=100)
        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr, ifaddr3))

    def test_route_replace_not_existing(self):
        # route('replace', ...) should succeed, if route doesn't exist
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        self.ip.route('replace',
                      dst=naddr,
                      mask=24,
                      gateway=ifaddr2,
                      table=100)
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr, ifaddr2))
        self.ip.flush_routes(table=100)
        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr, ifaddr2))

    def test_flush_routes(self):
        require_user('root')
        naddr1 = str(self.ipnets[1].network)
        naddr2 = str(self.ipnets[2].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        self.ip.route('add',
                      dst=naddr1,
                      mask=24,
                      gateway=ifaddr2,
                      table=100)
        self.ip.route('add',
                      dst=naddr2,
                      mask=24,
                      gateway=ifaddr2,
                      table=100)

        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr1, ifaddr2))
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr2, ifaddr2))

        self.ip.flush_routes(table=100, family=socket.AF_INET6)

        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr1, ifaddr2))
        assert grep('ip route show table 100',
                    pattern='%s/24.*%s' % (naddr2, ifaddr2))

        self.ip.flush_routes(table=100, family=socket.AF_INET)

        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr1, ifaddr2))
        assert not grep('ip route show table 100',
                        pattern='%s/24.*%s' % (naddr2, ifaddr2))

    def test_route_table_2048(self):
        require_user('root')
        naddr = str(self.ipnets[1].network)
        ifaddr1 = self.ifaddr()
        ifaddr2 = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], address=ifaddr1, mask=24)
        self.ip.route('add',
                      dst=naddr,
                      mask=24,
                      gateway=ifaddr2,
                      table=2048)
        assert grep('ip route show table 2048',
                    pattern='%s/24.*%s' % (naddr, ifaddr2))
        remove_link('bala')

    def test_symbolic_flags_ifaddrmsg(self):
        require_user('root')
        ifaddr = self.ifaddr()
        self.ip.link('set', index=self.ifaces[0], state='up')
        self.ip.addr('add', self.ifaces[0], ifaddr, 24)
        addr = [x for x in self.ip.get_addr()
                if x.get_attr('IFA_LOCAL') == ifaddr][0]
        assert 'IFA_F_PERMANENT' in addr.flags2names(addr['flags'])

    def test_symbolic_flags_ifinfmsg(self):
        require_user('root')
        self.ip.link('set', index=self.ifaces[0], flags=['IFF_UP'])
        iface = self.ip.get_links(self.ifaces[0])[0]
        assert iface['flags'] & 1
        assert 'IFF_UP' in iface.flags2names(iface['flags'])
        self.ip.link('set', index=self.ifaces[0], flags=['!IFF_UP'])
        assert not (self.ip.get_links(self.ifaces[0])[0]['flags'] & 1)

    def test_updown_link(self):
        require_user('root')
        try:
            for i in self.ifaces:
                self.ip.link('set', index=i, state='up')
        except NetlinkError:
            pass
        assert self.ip.get_links(*self.ifaces)[0]['flags'] & 1
        try:
            for i in self.ifaces:
                self.ip.link('set', index=i, state='down')
        except NetlinkError:
            pass
        assert not (self.ip.get_links(*self.ifaces)[0]['flags'] & 1)

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

    def test_link_filter(self):
        links = self.ip.link('dump', ifname='lo')
        assert len(links) == 1
        assert links[0].get_attr('IFLA_IFNAME') == 'lo'

    def test_link_legacy_nla(self):
        require_user('root')
        dev = self.ifaces[0]
        try:
            self.ip.link('set', index=dev, state='down')
            self.ip.link('set', index=dev, IFLA_IFNAME='bala')
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='bala')) == 1
        try:
            self.ip.link('set', index=dev, ifname=self.dev)
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname=self.dev)) == 1

    def test_link_rename(self):
        require_user('root')
        dev = self.ifaces[0]
        try:
            self.ip.link('set', index=dev, ifname='bala')
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='bala')) == 1
        try:
            self.ip.link('set', index=dev, ifname=self.dev)
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname=self.dev)) == 1

    def test_link_arp_flag(self):
        require_user('root')
        dev = self.ifaces[0]
        # by default dummy interface have NOARP set
        assert self.ip.get_links(dev)[0]['flags'] & IFF_NOARP
        self.ip.link('set', index=dev, arp=True)
        assert not self.ip.get_links(dev)[0]['flags'] & IFF_NOARP
        self.ip.link('set', index=dev, arp=False)
        assert self.ip.get_links(dev)[0]['flags'] & IFF_NOARP

    def test_rules(self):
        assert len(get_ip_rules('-4')) == \
            len(self.ip.get_rules(socket.AF_INET))
        assert len(get_ip_rules('-6')) == \
            len(self.ip.get_rules(socket.AF_INET6))

    def test_one_link(self):
        lo = self.ip.get_links(1)[0]
        assert lo.get_attr('IFLA_IFNAME') == 'lo'

    def test_default_routes(self):
        assert len(get_ip_default_routes()) == \
            len(self.ip.get_default_routes(family=socket.AF_INET, table=254))

    def test_routes(self):
        routes = list(self.ip.get_routes(family=socket.AF_INET, table=255))
        assert len(routes)
        assert all([isinstance(x, dict) for x in routes])
        assert all([x['event'] == 'RTM_NEWROUTE' for x in routes])
