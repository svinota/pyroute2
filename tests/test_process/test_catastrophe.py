import os
import signal
import time

import pytest

from pyroute2.process import ChildProcess


def child_process_timeout(x):
    time.sleep(x)


@pytest.mark.parametrize('sl', (1, 7, 23))
def test_timeout(sl):
    cp = ChildProcess(child_process_timeout, [sl])
    ts_start = time.time()
    with pytest.raises(TimeoutError):
        cp.run()
        cp.communicate(timeout=0.1)
    assert time.time() - ts_start < 1
    assert cp.exitcode == -signal.SIGKILL
    cp.close()


def child_process_kill(x):
    os.kill(os.getpid(), x)


@pytest.mark.parametrize('sg', (signal.SIGTERM, signal.SIGKILL))
def test_kill(sg):
    cp = ChildProcess(child_process_kill, [sg])
    ts_start = time.time()
    with pytest.raises(RuntimeError):
        cp.run()
        cp.communicate(timeout=0.1)
    assert time.time() - ts_start < 1
    assert cp.exitcode == -sg
