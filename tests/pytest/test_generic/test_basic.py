import os
import pytest
from contextlib import ExitStack
from pyroute2 import GenericNetlinkSocket
from pyroute2 import TaskStats
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
