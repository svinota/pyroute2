import time
import subprocess
from pyroute2 import IPDB
from pyroute2 import NetNS
from pyroute2 import netns as netnsmod
from uuid import uuid4
from utils import require_user


class TestNetNS(object):

    def test_create(self):
        require_user('root')

        nsid = str(uuid4())
        ipdb_main = IPDB()
        ipdb_test = IPDB(nl=NetNS(nsid))

        # create VETH pair
        ipdb_main.create(ifname='v0p0', kind='veth', peer='v0p1').commit()

        # move the peer to netns
        with ipdb_main.interfaces.v0p1 as veth:
            veth.net_ns_fd = nsid

        # assign addresses
        with ipdb_main.interfaces.v0p0 as veth:
            veth.add_ip('172.16.200.1/24')
            veth.up()

        with ipdb_test.interfaces.v0p1 as veth:
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
        ret_arp = '172.16.200.1' in list(ipdb_test.interfaces.v0p1.neighbors)
        # ret_arp = list(ipdb_test.interfaces.v0p1.neighbors)

        # cleanup
        ipdb_main.interfaces.v0p0.remove().commit()
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

        # create
        ipdb_main.create(kind='veth',
                         ifname='v0p0',
                         peer='v0p1',
                         mtu=mtu,
                         txqlen=txqlen).commit()

        # move
        with ipdb_main.interfaces['v0p1'] as veth:
            veth.net_ns_fd = nsid

        # set it up
        with ipdb_test.interfaces['v0p1'] as veth:
            veth.add_ip('fdb3:84e5:4ff4:55e4::1/64')
            veth.add_ip('fdff:ffff:ffff:ffc0::1/64')
            veth.mtu = mtu
            veth.txqlen = txqlen
            veth.up()
            veth.ifname = 'bala'

        veth = ipdb_test.interfaces.get('bala', None)
        ipdb_main.release()
        ipdb_test.release()
        netnsmod.remove(nsid)

        # check everything
        assert ('fdb3:84e5:4ff4:55e4::1', 64) in veth.ipaddr
        assert ('fdff:ffff:ffff:ffc0::1', 64) in veth.ipaddr
        assert veth.flags & 1
        assert veth.mtu == mtu
        assert veth.txqlen == txqlen
