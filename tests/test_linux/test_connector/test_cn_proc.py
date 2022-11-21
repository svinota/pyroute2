import os
import signal
import subprocess

import pytest
from pr2test.marks import require_root

from pyroute2 import ProcEventSocket
from pyroute2.netlink.connector.cn_proc import (
    PROC_EVENT_EXEC,
    PROC_EVENT_EXIT,
    PROC_EVENT_FORK,
)

pytestmark = [require_root()]


class ProcContext:
    def __init__(self, ps):
        self.ps = ps
        self.ps.bind()
        self.ps.control(listen=True)
        self.child = subprocess.Popen('true')
        self.child.wait()
        self.events = []
        for _ in range(1000):
            if self.match(
                what=PROC_EVENT_EXIT,
                process_pid=self.child.pid,
                source=self.ps.get(),
            ):
                return

    def push(self, event):
        self.events.append(event)

    def match(self, what, source=None, **kwarg):
        if source:
            source = tuple(source)
            self.events.extend(source)
        for event in source or self.events:
            if event['what'] == what:
                for key, value in kwarg.items():
                    if event[key] != value:
                        break
                else:
                    return True
        return False


@pytest.fixture
def cn_proc_context():
    with ProcEventSocket() as ps:
        yield ProcContext(ps)


def test_event_fork(cn_proc_context):
    assert cn_proc_context.match(
        what=PROC_EVENT_FORK,
        parent_pid=os.getpid(),
        child_pid=cn_proc_context.child.pid,
    )


def test_event_exec(cn_proc_context):
    assert cn_proc_context.match(
        what=PROC_EVENT_EXEC, process_pid=cn_proc_context.child.pid
    )


def test_event_exit(cn_proc_context):
    assert cn_proc_context.match(
        what=PROC_EVENT_EXIT,
        process_pid=cn_proc_context.child.pid,
        exit_code=0,
        exit_signal=signal.SIGCHLD,
    )
