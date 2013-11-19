try:
    import Queue
except ImportError:
    import queue as Queue
from pyroute2 import IPRoute
from utils import conflict_arch


class TestPtrace(object):

    def setup(self):
        self.ip = IPRoute(do_connect=False)

    def teardown(self):
        self.ip.release()

    def _test_launch(self):
        conflict_arch('arm')
        queue = self.ip.connect('ptrace://ip link show', no_stdout=True)
        while True:
            try:
                self.ip.get(queue, raw=True)
            except Queue.Empty:
                break
