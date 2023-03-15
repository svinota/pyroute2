import gc
import os

from pyroute2 import Ethtool


def get_fds():
    return set(os.listdir(f'/proc/{os.getpid()}/fd'))


def test_pipe_leak():
    fds = get_fds()
    etht = Ethtool()
    etht.close()
    gc.collect()
    assert get_fds() == fds
