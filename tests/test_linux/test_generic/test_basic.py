import os
from contextlib import ExitStack

import pytest

from pyroute2 import GenericNetlinkSocket, TaskStats
from pyroute2.netlink import nlmsg


def test_bind_first():
    with ExitStack() as sockets:
        ts = sockets.enter_context(TaskStats())
        gs = sockets.enter_context(GenericNetlinkSocket())

        with pytest.raises(RuntimeError) as ets:
            ts.get_pid_stat(os.getpid())

        with pytest.raises(RuntimeError) as egs:
            gs.nlm_request(nlmsg(), gs.prid)

        assert ets.value.args == egs.value.args
