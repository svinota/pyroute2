import os

from pr2test.marks import require_root

from pyroute2 import TaskStats

pytestmark = [require_root()]


def test_basic():
    with TaskStats() as ts:
        ts.bind()
        ret = ts.get_pid_stat(os.getpid())[0]

        pid = ret.get_nested('TASKSTATS_TYPE_AGGR_PID', 'TASKSTATS_TYPE_PID')
        stats = ret.get_nested(
            'TASKSTATS_TYPE_AGGR_PID', 'TASKSTATS_TYPE_STATS'
        )

        assert stats['cpu_count'] > 0
        assert stats['ac_pid'] == pid == os.getpid()
        assert stats['coremem'] > 0
        assert stats['virtmem'] > 0
