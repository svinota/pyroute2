import atexit
import errno
import gc
import getpass
import os
import resource

import pytest

from pyroute2 import IPRoute, AsyncIPRoute, netns
from pyroute2.common import uifname

RESPAWNS = 200
pytestmark = [
    pytest.mark.skipif(getpass.getuser() != 'root', reason='no root access')
]


@pytest.fixture
def resources():
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
    # restore limits
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    assert len(fds_after) <= len(fds_before)


def test_respawn_iproute_sync(resources):
    for _ in range(RESPAWNS):
        with IPRoute() as i:
            i.bind()
            i.link_lookup(ifname='lo')


@pytest.mark.asyncio
async def test_respawn_iproute_async(resources):
    for _ in range(RESPAWNS):
        async with AsyncIPRoute() as i:
            await i.bind()
            await i.link_lookup(ifname='lo')


def test_fd_leaks_netns(resources):
    for i in range(RESPAWNS):
        nsid = 'leak_%i' % i
        ipr = IPRoute(netns=nsid)
        ipr.link_lookup(ifname='lo')
        ipr.close()
        netns.remove(nsid)


def test_fd_leaks_netns_enoent(resources):
    for i in range(RESPAWNS):
        nsid = 'non_existent_leak_%i' % i
        try:
            with IPRoute(netns=nsid, flags=0):
                pass
        except OSError as e:
            fds = os.listdir(f'/proc/{os.getpid()}/fd/')
            assert e.errno == errno.ENOENT
