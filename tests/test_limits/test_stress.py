import atexit
import errno
import gc
import getpass
import os
import resource

import pytest

from pyroute2 import NDB, IPRoute, NetNS
from pyroute2.common import uifname

RESPAWNS = 200
pytestmark = [
    pytest.mark.skipif(getpass.getuser() != 'root', reason='no root access')
]


@pytest.fixture
def fds():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(
            resource.RLIMIT_NOFILE,
            (min(soft, RESPAWNS // 2), min(hard, RESPAWNS // 2)),
        )
    except ValueError:
        pytest.skip('cannot set RLIMIT_NOFILE')
    fds_before = os.listdir(f'/proc/{os.getpid()}/fd/')
    yield fds_before
    gc.collect()
    fds_after = os.listdir(f'/proc/{os.getpid()}/fd/')
    assert len(fds_after) <= len(fds_before)


def test_respawn_iproute_sync(fds):
    for _ in range(RESPAWNS):
        with IPRoute() as i:
            i.bind()
            i.link_lookup(ifname='lo')


def test_respawn_iproute_async(fds):
    for _ in range(RESPAWNS):
        with IPRoute() as i:
            i.bind(async_cache=True)
            i.link_lookup(ifname='lo')


def test_respawn_ndb(fds):
    for _ in range(RESPAWNS):
        with NDB() as i:
            assert i.interfaces.count() > 0
            assert i.addresses.count() > 0
            assert i.routes.count() > 0
            assert i.neighbours.count() > 0


def test_bridge_fd_leaks(fds):
    ifs = []
    for _ in range(RESPAWNS):
        ifs.append(uifname())
    with NDB() as ndb:
        for name in ifs:
            ndb.interfaces.create(ifname=name, kind='bridge').apply()
    with NDB() as ndb:
        for name in ifs:
            ndb.interfaces[name].remove().apply()


def test_tuntap_fd_leaks(fds):
    ifs = []
    for _ in range(RESPAWNS):
        ifs.append(uifname())
    with NDB() as ndb:
        for name in ifs:
            ndb.interfaces.create(
                ifname=name, kind='tuntap', mode='tun'
            ).apply()
    with NDB() as ndb:
        for name in ifs:
            ndb.interfaces[name].remove().apply()


def test_fd_leaks(fds):
    for i in range(RESPAWNS):
        nsid = 'leak_%i' % i
        ns = NetNS(nsid)
        ns.close()
        ns.remove()
        if hasattr(atexit, '_exithandlers'):
            assert ns.close not in atexit._exithandlers


def test_fd_leaks_nonexistent_ns(fds):
    for i in range(RESPAWNS):
        nsid = 'non_existent_leak_%i' % i
        try:
            with NetNS(nsid, flags=0):
                pass
        except OSError as e:
            assert e.errno in (errno.ENOENT, errno.EPIPE)
