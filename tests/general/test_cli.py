import io
import os
import threading
from pyroute2 import Console
from pyroute2 import IPDB
from utils import require_user
from nose.plugins.skip import SkipTest
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

scripts = {}
try:
    os.chdir('examples/cli')
except:
    raise SkipTest('test scripts not found')

for name in os.listdir('.'):
    with open(name, 'r') as f:
        scripts[name] = f.read()
os.chdir('../..')


class TestBasic(object):

    def readfunc(self, prompt):
        ret = self.queue.get()
        if ret is None:
            raise Exception("EOF")
        else:
            return ret

    def setup(self):
        self.ipdb = IPDB()
        self.io = io.BytesIO()
        self.queue = Queue()
        self.con = Console(stdout=self.io)
        self.con.isatty = False
        self.thread = threading.Thread(target=self.con.interact,
                                       args=[self.readfunc, ])
        self.thread.start()

    def feed(self, script):
        for line in script.split("\n"):
            self.queue.put(line)
        self.queue.put(None)
        self.thread.join()
        self.io.flush()

    def teardown(self):
        self.ipdb.release()

    # 8<---------------- test routines ------------------------------

    def test_dump_lo(self):
        self.feed(scripts['test_dump_lo'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:00:00:00:00:00'
        assert interface['ipaddr'][0][0] == '127.0.0.1'
        assert interface['ipaddr'][0][1] == 8

    def test_ensure(self):
        require_user('root')
        self.feed(scripts['test_ensure'])
        assert 'test01' in self.ipdb.interfaces
        assert ('172.16.189.5', 24) in self.ipdb.interfaces.test01.ipaddr
        self.ipdb.interfaces.test01.remove().commit()

    def test_comments_bang(self):
        require_user('root')
        self.feed(scripts['test_comments_bang'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'

    def test_comments_hash(self):
        require_user('root')
        self.feed(scripts['test_comments_hash'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'

    def test_comments_mixed(self):
        require_user('root')
        self.feed(scripts['test_comments_mixed'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'
