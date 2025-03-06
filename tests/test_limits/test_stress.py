import errno
import gc
import getpass
import os
import resource

import pytest

from pyroute2 import AsyncIPRoute, IPRoute, netns

RESPAWNS = 1024
USAGE_RSS = set()
pytestmark = [
    pytest.mark.skipif(getpass.getuser() != 'root', reason='no root access')
]


def reset_rss_usage():
    global USAGE_RSS
    USAGE_RSS = set()


def max_rss_usage():
    global USAGE_RSS
    usage = resource.getrusage(resource.RUSAGE_SELF)
    USAGE_RSS.add(usage.ru_maxrss // 10)
    return (max(USAGE_RSS) - min(USAGE_RSS)) == 0


@pytest.fixture
def resources():
    # current file limits
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    # current usage
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
    reset_rss_usage()
    for _ in range(RESPAWNS):
        with IPRoute() as i:
            i.bind()
            i.link_lookup(ifname='lo')
        assert max_rss_usage()
        gc.collect()


@pytest.mark.asyncio
async def test_respawn_iproute_async(resources):
    reset_rss_usage()
    for _ in range(RESPAWNS):
        async with AsyncIPRoute() as i:
            await i.bind()
            await i.link_lookup(ifname='lo')
        assert max_rss_usage()
        gc.collect()


def test_fd_leaks_netns(resources):
    reset_rss_usage()
    for i in range(RESPAWNS):
        nsid = 'leak_%i' % i
        ipr = IPRoute(netns=nsid)
        ipr.link_lookup(ifname='lo')
        ipr.close()
        assert max_rss_usage()
        gc.collect()
        netns.remove(nsid)


def test_fd_leaks_netns_enoent(resources):
    reset_rss_usage()
    for i in range(RESPAWNS):
        nsid = 'non_existent_leak_%i' % i
        try:
            with IPRoute(netns=nsid, flags=0):
                pass
        except OSError as e:
            assert e.errno == errno.ENOENT
        assert max_rss_usage()
        gc.collect()
