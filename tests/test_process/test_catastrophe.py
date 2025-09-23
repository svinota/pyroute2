import os
import time
from signal import SIGKILL, SIGTERM

import pytest

from pyroute2.process import ChildProcess


def child_process_timeout(x):
    time.sleep(x)


def child_process_die(x):
    os.kill(os.getpid(), x)


@pytest.mark.parametrize(
    'func,argv,catch,kill,exitcode',
    (
        (child_process_timeout, [1], TimeoutError, None, -SIGKILL),
        (child_process_timeout, [7], TimeoutError, None, -SIGKILL),
        (child_process_timeout, [23], TimeoutError, None, -SIGKILL),
        (child_process_die, [SIGTERM], RuntimeError, None, -SIGTERM),
        (child_process_die, [SIGKILL], RuntimeError, None, -SIGKILL),
        (child_process_timeout, [30], RuntimeError, SIGTERM, -SIGTERM),
        (child_process_timeout, [30], RuntimeError, SIGKILL, -SIGKILL),
    ),
    ids=[
        'timeout-1',
        'timeout-7',
        'timeout-23',
        'die-SIGTERM',
        'die-SIGKILL',
        'kill-SIGTERM',
        'kill-SIGKILL',
    ],
)
def test_child_fail(func, argv, catch, kill, exitcode):
    cp = ChildProcess(func, argv)
    ts_start = time.time()
    with pytest.raises(catch):
        cp.run()
        if kill is not None:
            os.kill(cp.pid, kill)
        cp.communicate(timeout=0.1)
    assert time.time() - ts_start < 1
    assert cp.exitcode == exitcode
    cp.close()
