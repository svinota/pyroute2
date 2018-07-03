import atexit
import errno
import resource
import threading
from pyroute2 import IPRoute
from pyroute2 import IPDB
from pyroute2 import NetNS
from pyroute2 import NDB
from pyroute2.common import uifname
from utils import require_user
from utils import count_socket_fds

RESPAWNS = 1200


class _TestIPDBRaces(object):

    def setup(self):
        self.ip = IPDB()

    def teardown(self):
        self.ip.release()

    def test_initdb(self):
        tnum = len(threading.enumerate())
        for _ in range(RESPAWNS):
            len(self.ip.interfaces.keys())
            len(self.ip.routes.keys())
            len(self.ip.rules.keys())
            self.ip.initdb()
            assert len(threading.enumerate()) <= tnum

    def _ports_mtu_race(self, kind):
        require_user('root')
        port1 = (self.ip
                 .create(ifname=uifname(), kind='dummy', mtu=1280)
                 .commit())
        port2 = (self.ip
                 .create(ifname=uifname(), kind='dummy')
                 .commit())
        master = (self.ip
                  .create(ifname=uifname(), kind=kind)
                  .commit())

        try:
            master.add_port(port1).commit()
            master.add_port(port2).commit()
        except:
            raise
        finally:
            port1.remove().commit()
            port2.remove().commit()
            master.remove().commit()

    def test_bridge_mtu(self):
        for _ in range(300):
            self._ports_mtu_race('bridge')


class TestRespawn(object):

    def test_respawn_iproute_sync(self):
        for _ in range(RESPAWNS):
            with IPRoute() as i:
                i.bind()
                i.link_lookup(ifname='lo')

    def test_respawn_iproute_async(self):
        for _ in range(RESPAWNS):
            with IPRoute() as i:
                i.bind(async_cache=True)
                i.link_lookup(ifname='lo')

    def test_respawn_ipdb(self):
        for _ in range(RESPAWNS):
            with IPDB() as i:
                len(i.interfaces.keys())
                len(i.routes.keys())
                len(i.rules.keys())
                pass


class TestIfs(object):

    def test_bridge_fd_leaks(self):
        ifs = []

        for _ in range(RESPAWNS):
            ifs.append(uifname())

        with IPDB() as ipdb:
            for name in ifs:
                ipdb.create(ifname=name, kind="bridge").commit()

        with IPDB() as ipdb:
            for name in ifs:
                ipdb.interfaces[name].remove().commit()

    def test_tuntap_fd_leaks(self):
        ifs = []

        for _ in range(RESPAWNS):
            ifs.append(uifname())

        with IPRoute() as ipr:
            for name in ifs:
                ipr.link("add", ifname=name, kind="tuntap", mode="tun")

        with IPDB() as ipdb:
            for name in ifs:
                ipdb.interfaces[name].remove().commit()


class TestNetNS(object):

    def setup(self):
        self._nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
        soft, hard = self._nofile
        new_limit = (min(soft, RESPAWNS / 2), min(hard, RESPAWNS / 2))
        resource.setrlimit(resource.RLIMIT_NOFILE, new_limit)
        self._socket_fd_count = count_socket_fds()

    def teardown(self):
        resource.setrlimit(resource.RLIMIT_NOFILE, self._nofile)
        assert self._socket_fd_count == count_socket_fds()

    def test_fd_leaks(self):
        for i in range(RESPAWNS):
            nsid = 'leak_%i' % i
            ns = NetNS(nsid)
            ns.close()
            ns.remove()
            if hasattr(atexit, '_exithandlers'):
                assert ns.close not in atexit._exithandlers

    def test_fd_leaks_nonexistent_ns(self):
        for i in range(RESPAWNS):
            nsid = 'non_existent_leak_%i' % i
            try:
                with NetNS(nsid, flags=0):
                    pass
            except OSError as e:
                assert e.errno in (errno.ENOENT, errno.EPIPE)
