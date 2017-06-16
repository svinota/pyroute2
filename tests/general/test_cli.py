import io
import threading
from pyroute2 import Console
from pyroute2 import IPDB
try:
    from Queue import Queue
except ImportError:
    from queue import Queue


script1 = """
! a script simply to dump the loopback interface
!
interfaces
    lo
        dump
"""

script2 = """
! create a dummy interface with an address on it
!
create ifname=test01 kind=dummy
interfaces
    test01
        add_ip 172.16.189.5/24
        up
        commit

! rollback any transaction that makes the address
! unavailable
!
ensure reachable=172.16.189.5

! try to remove the interface: the transaction
! must fail
!
interfaces
    test01
        remove
        commit
"""


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

    def test_dump_lo(self):
        self.feed(script1)

        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:00:00:00:00:00'
        assert interface['ipaddr'][0][0] == '127.0.0.1'
        assert interface['ipaddr'][0][1] == 8

    def test_ensure(self):
        self.feed(script2)

        assert 'test01' in self.ipdb.interfaces
        assert ('172.16.189.5', 24) in self.ipdb.interfaces.test01.ipaddr
        self.ipdb.interfaces.test01.remove().commit()
