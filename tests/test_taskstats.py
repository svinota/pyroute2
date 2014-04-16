from pyroute2 import TaskStats
from utils import require_user


class TestTaskStats(object):

    def setup(self):
        self.ts = TaskStats()

    def teardown(self):
        self.ts.release()

    def test_get_pid_stat(self):
        require_user('root')
        ret = self.ts.get_pid_stat(1)[0]
        assert ret.get_attr('TASKSTATS_TYPE_AGGR_PID').\
            get_attr('TASKSTATS_TYPE_PID') == 1
