import gc
import os

from pyroute2 import Ethtool


def get_fds():
    fd = os.open(f'/proc/{os.getpid()}/fd', os.O_RDONLY)
    try:
        return set(os.listdir(fd)) - {fd}
    finally:
        os.close(fd)


def test_pipe_leak():
    fds = get_fds()
    etht = Ethtool()
    etht.close()
    gc.collect()
    assert get_fds() == fds


def test_context_manager():
    fds = get_fds()
    with Ethtool():
        pass
    gc.collect()
    assert get_fds() == fds
