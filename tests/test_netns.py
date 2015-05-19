import os
import time
import subprocess
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

    def test_create(self):
        require_user('root')

        nsid = str(uuid4())
        ipdb_main = IPDB()
        ipdb_test = IPDB(nl=NetNS(nsid))
        if1 = uifname()
        if2 = uifname()

        # create VETH pair
        ipdb_main.create(ifname=if1, kind='veth', peer=if2).commit()

        # move the peer to netns
        with ipdb_main.interfaces[if2] as veth:
            veth.net_ns_fd = nsid

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
        ret_arp = '172.16.200.1' in list(ipdb_test.interfaces[if2].neighbors)
        # ret_arp = list(ipdb_test.interfaces.v0p1.neighbors)

        # cleanup
        ipdb_main.interfaces[if1].remove().commit()
        ipdb_main.release()
        ipdb_test.release()
        netnsmod.remove(nsid)

        assert ret_ping
        assert ret_arp
        assert nsid not in netnsmod.listnetns()

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
