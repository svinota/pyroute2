import io
import threading
from pyroute2 import Console
from pyroute2 import IPDB
from utils import require_user
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

#
# test_dump_lo
#
script01 = """
!
! A script simply to dump the loopback interface.
!
interfaces
    lo
        dump
"""

#
# test_ensure
#
script02 = """
!
! Create a dummy interface with an address on it.
! Notice that the interface doesn't appear on the
! system before the commit call.
!
create ifname=test01 kind=dummy
interfaces
    test01
        add_ip 172.16.189.5/24
        up
        commit

! Rollback any transaction that makes the address
! unavailable:
!
ensure reachable=172.16.189.5

! Try to remove the interface, the transaction
! must fail:
!
interfaces
    test01
        remove
        commit

! Here we check with an external tools that the
! interface still exists.
!
"""

#
# test_comments_bang
#
script03 = """
!
! Test comments start with !
!
create ifname=test01 kind=dummy address=00:11:22:33:44:55
commit
!
interfaces ! ... tail comments
    !
    ! ... indented comments
    !
    test01
        !
        dump
        !
        remove
        commit
"""

#
# test_comments_hash
#
script04 = """
#
# Test comments start with #
#
create ifname=test01 kind=dummy address=00:11:22:33:44:55
commit
#
interfaces # ... tail comments
    #
    # ... indented comments
    #
    test01
        #
        dump
        #
        remove
        commit
"""

#
# test_comments_mixed
#
script05 = """
#
! Test mixed comments, both ! and #
#
create ifname=test01 kind=dummy address=00:11:22:33:44:55
commit
!
interfaces # ... tail comments
    !
    # ... indented comments
    !
    test01
        #
        dump
        !
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

    # 8<---------------- test routines ------------------------------

    def test_dump_lo(self):
        self.feed(script01)
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:00:00:00:00:00'
        assert interface['ipaddr'][0][0] == '127.0.0.1'
        assert interface['ipaddr'][0][1] == 8

    def test_ensure(self):
        require_user('root')
        self.feed(script02)
        assert 'test01' in self.ipdb.interfaces
        assert ('172.16.189.5', 24) in self.ipdb.interfaces.test01.ipaddr
        self.ipdb.interfaces.test01.remove().commit()

    def test_comments_bang(self):
        require_user('root')
        self.feed(script03)
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'

    def test_comments_hash(self):
        require_user('root')
        self.feed(script04)
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'

    def test_comments_mixed(self):
        require_user('root')
        self.feed(script05)
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'
