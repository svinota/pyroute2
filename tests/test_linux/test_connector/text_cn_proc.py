import os
import subprocess

import pytest
from pr2test.marks import require_root

from pyroute2 import ProcEventSocket
from pyroute2.netlink.connector.cn_proc import PROC_EVENT_EXIT, PROC_EVENT_FORK


class ProcContext:
    def __init__(self, ps):
        self.ps = ps
        self.ps.bind()
        self.ps.control(listen=True)
        self.child = subprocess.Popen('true')
        self.child.wait()
        self.events = []
        for _ in range(1000):
            for event in self.ps.get():
                self.push(event)
                if (
                    event['what'] == PROC_EVENT_EXIT
                    and event['process_pid'] == self.child.pid
                ):
                    return

    def push(self, event):
        self.events.append(event)


@pytest.fixture
def cn_proc_context():
    with ProcEventSocket() as ps:
        yield ProcContext(ps)


@require_root
def test_event_fork(cn_proc_context):
    for event in cn_proc_context.events:
        if (
            event['what'] == PROC_EVENT_FORK
            and event['parent_pid'] == os.getpid()
            and event['child_pid'] == cn_proc_context.child.pid
        ):
            break
    else:
        raise Exception('expected event not received')
