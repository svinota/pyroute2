import os
import sys
import time
from threading import Thread
from utils import require_user
from utils import require_8021q
from utils import require_bridge
from utils import require_bond
from nose.plugins.skip import SkipTest
from pyroute2.netlink import NetlinkError

from importlib import import_module
try:
    from Queue import Queue
except ImportError:
    from queue import Queue


class TestExamples(object):

    def setup(self):
        self.pwd = os.getcwd()
        os.chdir('../examples/')
        newdir = os.getcwd()
        if newdir not in sys.path:
            sys.path.append(newdir)
        self.feedback = Queue()
        self.pr, self.pw = os.pipe()
        __builtins__['pr2_sync'] = self.pr

    def teardown(self):
        os.chdir(self.pwd)
        os.close(self.pr)
        os.close(self.pw)

    def launcher(self, client, server=None):

        client_error = None
        server_error = None

        def wrapper(parent, symbol):
            try:
                import_module(symbol)
                parent.feedback.put(None)
            except Exception as e:
                parent.feedback.put(e)

        if server is not None:
            s = Thread(target=wrapper, args=(self, server, ))
            s.start()
            time.sleep(1)

        c = Thread(target=wrapper, args=(self, client, ))
        c.start()
        client_error = self.feedback.get()

        if server is not None:
            os.write(self.pw, b'q')
            server_error = self.feedback.get()
            s.join()

        c.join()

        if any((client_error, server_error)):
            print("client error:")
            print(client_error)
            print("server error:")
            print(server_error)
            raise RuntimeError

    def test_create_bond(self):
        require_user('root')
        require_bond()
        self.launcher('create_bond')

    def test_create_interface(self):
        require_user('root')
        self.launcher('create_interface')

    def test_create_vlan(self):
        require_user('root')
        require_8021q()
        self.launcher('create_vlan')

    def test_ip_monitor(self):
        require_user('root')
        self.launcher('create_interface', server='ip_monitor')

    def test_ipdb_autobr(self):
        require_user('root')
        require_bridge()
        self.launcher('ipdb_autobr')

    def test_ipdb_chain(self):
        require_user('root')
        require_bond()
        self.launcher('ipdb_chain')

    def test_ipdb_precb(self):
        require_user('root')
        self.launcher('ipdb_precb')

    def test_ipdb_routes(self):
        require_user('root')
        self.launcher('ipdb_routes')

    def test_nla_operators(self):
        require_user('root')
        self.launcher('nla_operators')

    def test_nla_operators2(self):
        require_user('root')
        self.launcher('nla_operators2')

    def _test_taskstats(self):
        require_user('root')
        try:
            self.launcher('taskstats')
        except NetlinkError as x:
            if x.code == 2:
                raise SkipTest('missing taskstats support')
            else:
                raise

    def _test_pmonitor(self):
        require_user('root')
        try:
            self.launcher('pmonitor', server='server')
        except NetlinkError as x:
            if x.code == 2:
                raise SkipTest('missing taskstats support')
            else:
                raise
