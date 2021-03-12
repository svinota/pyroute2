import os
import time
import fcntl
import signal
import subprocess
import traceback
import tempfile
from threading import Thread

from pyroute2 import IPDB
from pyroute2 import IPRoute
from pyroute2 import NetNS
from pyroute2 import NSPopen
from pyroute2.common import uifname
from pyroute2.netns.process.proxy import NSPopen as NSPopenDirect
from pyroute2 import netns as netnsmod
from uuid import uuid4
from utils import require_user


class TestNSPopen(object):

    def setup(self):
        self.ip = IPRoute()
        self.names = []

    def teardown(self):
        self.ip.close()
        for ns in self.names:
            netnsmod.remove(ns)

    def alloc_nsname(self):
        nsid = str(uuid4())
        self.names.append(nsid)
        return nsid

    def test_stdio(self):
        require_user('root')
        nsid = self.alloc_nsname()
        nsp = NSPopen(nsid, ['ip', 'ad'],
                      flags=os.O_CREAT,
                      stdout=subprocess.PIPE)
        output = nsp.stdout.read()
        nsp.release()
        assert output is not None

    def test_fcntl(self):
        require_user('root')
        nsid = self.alloc_nsname()
        nsp = NSPopen(nsid, ['ip', 'ad'],
                      flags=os.O_CREAT,
                      stdout=subprocess.PIPE)
        flags = nsp.stdout.fcntl(fcntl.F_GETFL)
        nsp.release()
        assert flags == 0

    def test_api_class(self):
        api_nspopen = set(dir(NSPopenDirect))
        api_popen = set(dir(subprocess.Popen))
        assert api_nspopen & api_popen == api_popen

    def test_api_object(self):
        require_user('root')
        nsid = self.alloc_nsname()
        nsp = NSPopen(nsid, ['true'], flags=os.O_CREAT, stdout=subprocess.PIPE)
        smp = subprocess.Popen(['true'], stdout=subprocess.PIPE)
        nsp.communicate()
        smp.communicate()
        api_nspopen = set(dir(nsp))
        api_popen = set(dir(smp))
        minimal = set(('communicate', 'kill', 'wait'))
        assert minimal & (api_nspopen & api_popen) == minimal
        smp.wait()
        nsp.wait()
        assert nsp.returncode == smp.returncode == 0
        nsp.release()

    def test_release(self):
        require_user('root')
        nsid = self.alloc_nsname()
        nsp = NSPopen(nsid, ['true'], flags=os.O_CREAT, stdout=subprocess.PIPE)
        nsp.communicate()
        nsp.wait()
        nsp.release()
        try:
            print(nsp.returncode)
        except RuntimeError:
            pass

    def test_basic(self):
        require_user('root')
        nsid = self.alloc_nsname()
        # create NS and run a child
        nsp = NSPopen(nsid,
                      ['ip', '-o', 'link'],
                      stdout=subprocess.PIPE,
                      flags=os.O_CREAT)
        ret = nsp.communicate()[0].decode('utf-8')
        host_links = [x.get_attr('IFLA_IFNAME') for x in self.ip.get_links()]
        netns_links = [x.split(':')[1].split('@')[0].strip()
                       for x in ret.split('\n') if len(x)]
        assert nsp.wait() == nsp.returncode == 0
        assert set(host_links) & set(netns_links) == set(netns_links)
        assert set(netns_links) < set(host_links)
        assert not set(netns_links) > set(host_links)
        nsp.release()


class TestNetNS(object):

    def test_create_tuntap(self):
        require_user('root')
        # actually this test checks the nlsocket plugin feedback
        # in a pair of remote client/server
        foo = str(uuid4())
        tun = uifname()
        tap = uifname()

        with IPDB(nl=NetNS(foo)) as ip:
            ip.create(ifname=tun, kind='tuntap', mode='tun').commit()
            ip.create(ifname=tap, kind='tuntap', mode='tap').commit()
            assert tun in ip.interfaces.keys()
            assert tap in ip.interfaces.keys()
            ip.interfaces[tun].remove().commit()
            ip.interfaces[tap].remove().commit()
            assert tun not in ip.interfaces.keys()
            assert tap not in ip.interfaces.keys()

        netnsmod.remove(foo)

    def test_create_peer_attrs(self):
        require_user('root')
        foo = str(uuid4())
        bar = str(uuid4())
        ifA = uifname()
        ifB = uifname()
        netnsmod.create(foo)
        netnsmod.create(bar)

        with IPDB(nl=NetNS(foo)) as ip:
            ip.create(ifname=ifA,
                      kind='veth',
                      peer={'ifname': ifB,
                            'net_ns_fd': bar}).commit()
            assert ifA in ip.interfaces.keys()
            assert ifB not in ip.interfaces.keys()

        with IPDB(nl=NetNS(bar)) as ip:
            assert ifA not in ip.interfaces.keys()
            assert ifB in ip.interfaces.keys()
            ip.interfaces[ifB].remove().commit()
            assert ifA not in ip.interfaces.keys()
            assert ifB not in ip.interfaces.keys()

        with IPDB(nl=NetNS(foo)) as ip:
            assert ifA not in ip.interfaces.keys()
            assert ifB not in ip.interfaces.keys()

        netnsmod.remove(foo)
        netnsmod.remove(bar)

    def test_move_ns_pid(self):
        require_user('root')
        foo = str(uuid4())
        bar = str(uuid4())
        ifA = uifname()
        netnsmod.create(foo)
        netnsmod.create(bar)

        ns_foo = IPDB(nl=NetNS(foo))
        ns_bar = IPDB(nl=NetNS(bar))

        try:
            ns_foo.create(ifname=ifA, kind='dummy').commit()
            with ns_foo.interfaces[ifA] as iface:
                iface.net_ns_pid = ns_bar.nl.child

            assert ifA in ns_bar.interfaces.keys()
            assert ifA not in ns_foo.interfaces.keys()

            with ns_bar.interfaces[ifA] as iface:
                iface.net_ns_pid = ns_foo.nl.child

            assert ifA not in ns_bar.interfaces.keys()
            assert ifA in ns_foo.interfaces.keys()

        finally:
            ns_foo.release()
            ns_bar.release()
            netnsmod.remove(foo)
            netnsmod.remove(bar)

    def test_there_and_back(self):
        require_user('root')
        # wait until the previous test's side effects are gone
        time.sleep(2)
        #
        fd = open('/proc/self/ns/net', 'r')
        foo = str(uuid4())
        #
        # please notice, that IPRoute / IPDB, started in a netns, will continue
        # to work in a given netns even if the process changes to another netns
        #
        with IPRoute() as ip:
            links_main1 = set([x.get('index', None) for x in ip.get_links()])
        netnsmod.setns(foo)
        with IPRoute() as ip:
            links_foo = set([x.get('index', None) for x in ip.get_links()])
        netnsmod.setns(fd)
        with IPRoute() as ip:
            links_main2 = set([x.get('index', None) for x in ip.get_links()])
        assert links_main1 == links_main2
        assert links_main1 != links_foo
        netnsmod.remove(foo)
        fd.close()

    def test_move_ns_fd(self):
        require_user('root')
        foo = str(uuid4())
        bar = str(uuid4())
        ifA = uifname()
        ifB = uifname()
        netnsmod.create(foo)
        netnsmod.create(bar)

        with IPDB(nl=NetNS(foo)) as ip:
            ip.create(ifname=ifA, kind='veth', peer=ifB).commit()
            assert ifA in ip.interfaces.keys()
            assert ifB in ip.interfaces.keys()
            with ip.interfaces[ifB] as intf:
                intf.net_ns_fd = bar
            assert ifA in ip.interfaces.keys()
            assert ifB not in ip.interfaces.keys()

        with IPDB(nl=NetNS(bar)) as ip:
            assert ifA not in ip.interfaces.keys()
            assert ifB in ip.interfaces.keys()
            ip.interfaces[ifB].remove().commit()
            assert ifA not in ip.interfaces.keys()
            assert ifB not in ip.interfaces.keys()

        with IPDB(nl=NetNS(foo)) as ip:
            assert ifA not in ip.interfaces.keys()
            assert ifB not in ip.interfaces.keys()

        netnsmod.remove(foo)
        netnsmod.remove(bar)

    def _test_create(self, ns_name, ns_fd=None, pid=None):
        require_user('root')
        ipdb_main = IPDB()
        ipdb_test = IPDB(nl=NetNS(ns_name))

        if1 = uifname()
        if2 = uifname()

        # create VETH pair
        ipdb_main.create(ifname=if1, kind='veth', peer=if2).commit()

        # move the peer to netns
        with ipdb_main.interfaces[if2] as veth:
            veth.net_ns_fd = ns_fd or ns_name

        # assign addresses
        with ipdb_main.interfaces[if1] as veth:
            veth.add_ip('172.16.200.1/24')
            veth.up()

        with ipdb_test.interfaces[if2] as veth:
            veth.add_ip('172.16.200.2/24')
            veth.up()

        # ping peer
        try:
            with open('/dev/null', 'w') as fnull:
                subprocess.check_call(['ping', '-c', '1', '172.16.200.2'],
                                      stdout=fnull, stderr=fnull)
            ret_ping = True
        except Exception:
            ret_ping = False

        # check ARP
        time.sleep(0.5)
        ret_arp = '172.16.200.1' in list(ipdb_test.interfaces[if2].neighbours)
        # ret_arp = list(ipdb_test.interfaces.v0p1.neighbours)

        # cleanup
        ipdb_main.interfaces[if1].remove().commit()
        ipdb_main.release()
        ipdb_test.release()

        assert ret_ping
        assert ret_arp

    def test_pushns(self):
        require_user('root')
        foo = str(uuid4())
        ifA = uifname()

        with IPRoute() as ipr:
            ipr.link('add', ifname=ifA, kind='dummy')

        netnsmod.pushns(foo)
        with IPRoute() as ipr:
            assert ifA not in [x.get_attr('IFLA_IFNAME') for x
                               in ipr.link('dump')]
        netnsmod.popns()
        with IPRoute() as ipr:
            assert ifA in [x.get_attr('IFLA_IFNAME') for x
                           in ipr.link('dump')]

            ipr.link('del', index=ipr.link_lookup(ifname=ifA)[0])

        netnsmod.remove(foo)

    def test_create(self):
        ns_name = str(uuid4())
        self._test_create(ns_name)
        netnsmod.remove(ns_name)
        assert ns_name not in netnsmod.listnetns()

    def test_attach(self):
        ns_name = str(uuid4())
        pid = os.fork()
        if pid == 0:
            # child
            while True:
                time.sleep(.1)
        else:
            # parent
            try:
                self._test_create(ns_name, pid=pid)
            finally:
                os.kill(int(pid), signal.SIGTERM)
                os.waitpid(pid, 0)
        netnsmod.remove(ns_name)
        assert ns_name not in netnsmod.listnetns()

    def test_create_from_path(self):
        require_user('root')
        ns_dir = tempfile.mkdtemp()
        # Create namespace
        ns_name = str(uuid4())
        nspath = '%s/%s' % (ns_dir, ns_name)
        temp_ns = NetNS(nspath)
        temp_ns.close()
        fd = open(nspath)
        self._test_create(nspath, fd.fileno())
        fd.close()
        netnsmod.remove(nspath)
        assert ns_name not in netnsmod.listnetns()
        assert ns_name not in netnsmod.listnetns(ns_dir)

    def test_rename_plus_ipv6(self):
        require_user('root')

        mtu = 1280  # mtu must be >= 1280 if you plan to use IPv6
        txqlen = 2000
        nsid = str(uuid4())
        ipdb_main = IPDB()
        ipdb_test = IPDB(nl=NetNS(nsid))
        if1 = uifname()
        if2 = uifname()
        if3 = uifname()

        # create
        ipdb_main.create(kind='veth',
                         ifname=if1,
                         peer=if2,
                         mtu=mtu,
                         txqlen=txqlen).commit()

        # move
        with ipdb_main.interfaces[if2] as veth:
            veth.net_ns_fd = nsid

        # set it up
        with ipdb_test.interfaces[if2] as veth:
            veth.add_ip('fdb3:84e5:4ff4:55e4::1/64')
            veth.add_ip('fdff:ffff:ffff:ffc0::1/64')
            veth.mtu = mtu
            veth.txqlen = txqlen
            veth.up()
            veth.ifname = if3

        veth = ipdb_test.interfaces.get(if3, None)
        ipdb_main.release()
        ipdb_test.release()
        netnsmod.remove(nsid)

        # check everything
        assert ('fdb3:84e5:4ff4:55e4::1', 64) in veth.ipaddr
        assert ('fdff:ffff:ffff:ffc0::1', 64) in veth.ipaddr
        assert veth.flags & 1
        assert veth.mtu == mtu
        assert veth.txqlen == txqlen

    def test_multithread(self):
        require_user('root')

        parallel_count = 5
        test_count = 10

        ns_names = ['testns%i' % i for i in range(parallel_count)]

        success = []

        for ns_name in ns_names:
            NetNS(ns_name)

        for _t in range(test_count):
            threads = [
                Thread(target=_ns_worker,
                       args=(netnsmod._get_netnspath(ns_name), i, success))
                for i, ns_name in enumerate(ns_names)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        for ns_name in ns_names:
            netnsmod.remove(ns_name)

        assert all([x[0] for x in success])

    def test_ns_pids(self):
        def waiting_child(fd):
            while True:
                if not os.read(fd, 32):
                    exit(0)

        require_user('root')
        foo = str(uuid4())
        netnsmod.create(foo)
        netnsmod.pushns(foo)
        foo_pid, foo_fd = os.forkpty()
        if not foo_pid:
            waiting_child(foo_fd)
        netnsmod.popns()

        pids = netnsmod.ns_pids()
        ns_name = netnsmod.pid_to_ns(foo_pid)
        try:
            assert pids[foo] == [foo_pid]
            assert ns_name == foo
        finally:
            os.close(foo_fd)
            netnsmod.remove(foo)


def _ns_worker(netns_path, worker_index, success):
    with IPRoute() as ip, NetNS(netns_path) as ns:
        try:
            veth_outside = 'veth%s-o' % worker_index
            veth_inside = 'veth%s-i' % worker_index
            ip.link('add', ifname=veth_outside, kind='veth', peer=veth_inside)
            veth_outside_idx = ip.link_lookup(ifname=veth_outside)[0]
            ip.link('set', index=veth_outside_idx, state='up')
            veth_inside_idx = ip.link_lookup(ifname=veth_inside)[0]
            ip.link('set', index=veth_inside_idx, net_ns_fd=netns_path)
            veth_inside_idx = ns.link_lookup(ifname=veth_inside)[0]
            ns.link('set', index=veth_inside_idx, state='up')
            success.append((True, None))
        except Exception:
            success.append((False, traceback.format_exc(), netns_path))
        finally:
            if veth_outside_idx is not None:
                ip.link('del', index=veth_outside_idx)
