import os
import sys
import time
import subprocess
from utils import require_user
from utils import require_8021q
from utils import require_bridge
from utils import require_bond
from nose.plugins.skip import SkipTest
from pyroute2.netlink import NetlinkError

try:
    import importlib
except ImportError:
    importlib = None

# FIXME: for some unknown reason, this particular module
# has multiple issues with Python 3.2
if sys.version[:3] == '3.2':
    raise SkipTest('https://github.com/svinota/pyroute2/issues/42')


class TestExamples(object):

    def setup(self):
        self.pwd = os.getcwd()
        os.chdir('../examples/')
        newdir = os.getcwd()
        if newdir not in sys.path:
            sys.path.append(newdir)

    def teardown(self):
        os.chdir(self.pwd)

    def launcher(self, client, server=None):
        with open(os.devnull, 'w') as fnull:
            if server is not None:
                s = subprocess.Popen([sys.executable, server],
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=fnull)
                time.sleep(1)
            if importlib is not None:
                importlib.import_module(client)
            else:
                c = subprocess.Popen([sys.executable, client + '.py'],
                                     stdin=fnull,
                                     stdout=subprocess.PIPE,
                                     stderr=fnull)
                c.communicate()
            if server is not None:
                s.stdin.write(b'\n')
                s.communicate()
                assert s.returncode == 0
            if importlib is None:
                assert c.returncode == 0

    def test_client_server(self):
        self.launcher('client', server='server.py')

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

    def test_ioc_client_server(self):
        self.launcher('ioc_client', server='ioc_server.py')

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

    def test_push_pull_iocore(self):
        self.launcher('push_pull_iocore')

    def test_push_pull_rpc(self):
        self.launcher('push_pull_rpc')

    def test_req_rep(self):
        self.launcher('req_rep')

    def test_taskstats(self):
        require_user('root')
        try:
            self.launcher('taskstats')
        except NetlinkError as x:
            if x.code == 2:
                raise SkipTest('missing taskstats support')
            else:
                raise

    def test_pmonitor(self):
        require_user('root')
        try:
            self.launcher('pmonitor', server='server.py')
        except NetlinkError as x:
            if x.code == 2:
                raise SkipTest('missing taskstats support')
            else:
                raise
