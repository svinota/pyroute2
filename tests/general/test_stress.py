from pyroute2 import IPRoute
from pyroute2 import IPDB
from pyroute2 import NetNS
from nose.tools import assert_raises
import fcntl
import sys

RESPAWNS = 1200


class TestRespawn(object):

    def test_respawn_iproute_sync(self):
        for _ in range(RESPAWNS):
            with IPRoute() as i:
                i.bind()
                i.link_lookup(ifname='lo')

    def test_respawn_iproute_async(self):
        for _ in range(RESPAWNS):
            with IPRoute() as i:
                i.bind(async=True)
                i.link_lookup(ifname='lo')

    def test_respawn_ipdb(self):
        for _ in range(RESPAWNS):
            with IPDB():
                pass


class TestNetNS(object):

    def test_fd_leaks(self):
        namespaces = []
        for i in range(RESPAWNS):
            nsid = 'leak_%i' % i
            ns = NetNS(nsid)
            ns.close()
            ns.remove()
            namespaces.append(ns)
        if sys.version_info > (3, 2) and sys.version_info < (3, 6):
            for n in namespaces:
                assert_raises(OSError,
                              fcntl.fcntl, n.server.sentinel, fcntl.F_GETFD)
