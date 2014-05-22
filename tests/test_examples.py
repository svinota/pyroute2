import os
import sys
import time
import subprocess
from utils import require_user
from utils import require_8021q
from utils import require_bridge
from utils import require_bond


class TestExamples(object):

    def setup(self):
        self.pwd = os.getcwd()
        os.chdir('../examples/')

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
            c = subprocess.Popen([sys.executable, client],
                                 stdin=fnull,
                                 stdout=subprocess.PIPE,
                                 stderr=fnull)
            c.communicate()
            if server is not None:
                s.stdin.write(b'\n')
                s.communicate()
                assert s.returncode == 0

            assert c.returncode == 0

    def test_client_server(self):
        self.launcher('client.py', 'server.py')

    def test_create_bond(self):
        require_user('root')
        require_bond()
        self.launcher('create_bond.py')

    def test_create_interface(self):
        require_user('root')
        self.launcher('create_interface.py')

    def test_create_vlan(self):
        require_user('root')
        require_8021q()
        self.launcher('create_vlan.py')

    def test_ioc_client_server(self):
        self.launcher('ioc_client.py', 'ioc_server.py')

    def test_ipdb_autobr(self):
        require_user('root')
        require_bridge()
        self.launcher('ipdb_autobr.py')

    def test_ipdb_chain(self):
        require_user('root')
        require_bond()
        self.launcher('ipdb_chain.py')

    def test_ipdb_precb(self):
        require_user('root')
        self.launcher('ipdb_precb.py')

    def test_ipdb_routes(self):
        require_user('root')
        self.launcher('ipdb_routes.py')

    def test_nla_operators(self):
        require_user('root')
        self.launcher('nla_operators.py')

    def test_nla_operators2(self):
        require_user('root')
        self.launcher('nla_operators2.py')

    def test_push_pull_iocore(self):
        self.launcher('push_pull_iocore.py')

    def test_push_pull_rpc(self):
        self.launcher('push_pull_rpc.py')

    def test_req_rep(self):
        self.launcher('req_rep.py')

    def test_taskstats(self):
        require_user('root')
        self.launcher('taskstats.py')
