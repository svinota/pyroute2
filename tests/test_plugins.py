import Queue
from pyroute2 import IPRoute


class TestPtrace(object):

    def setup(self):
        self.ip = IPRoute(do_connect=False)

    def teardown(self):
        self.ip.release()

    def test_launch(self):

        queue = self.ip.connect('ptrace://ip link show', no_stdout=True)
        while True:
            try:
                self.ip.get(queue, raw=True)
            except Queue.Empty:
                break
