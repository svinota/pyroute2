import os
import sys
import time
import errno
import subprocess
from threading import Thread
from utils import require_user
from utils import skip_if_not_supported
from nose.plugins.skip import SkipTest
from pyroute2.common import uifname
from pyroute2.netlink.exceptions import NetlinkError

try:
    import imp
    from Queue import Queue

    def _import(symbol):
        return imp.load_module(symbol, *imp.find_module(symbol))

except ImportError:
    from queue import Queue
    from importlib import import_module

    def _import(symbol):
        return import_module(symbol)


def interface_event():
    with open(os.devnull, 'w') as fnull:
        p0 = uifname()
        add_command = 'ip link add dev %s type dummy' % p0
        del_command = 'ip link del dev %s' % p0
        subprocess.call(add_command.split(),
                        stdout=fnull,
                        stderr=fnull)
        subprocess.call(del_command.split(),
                        stdout=fnull,
                        stderr=fnull)


class TestExamples(object):

    def setup(self):
        self.pwd = os.getcwd()
        os.chdir('../examples/')
        newdir = os.getcwd()
        if newdir not in sys.path:
            sys.path.append(newdir)
        self.client_feedback = Queue()
        self.server_feedback = Queue()
        self.pr, self.pw = os.pipe()
        __builtins__['pr2_sync'] = self.pr

    def teardown(self):
        os.chdir(self.pwd)
        os.close(self.pr)
        os.close(self.pw)

    def launcher(self, client, server=None):

        client_error = None
        server_error = None

        def wrapper(parent, symbol, feedback):
            try:
                if symbol in globals():
                    globals()[symbol]()
                else:
                    _import(symbol)
                feedback.put(None)
            except Exception as e:
                feedback.put(e)

        if server is not None:
            s = Thread(target=wrapper, args=(self,
                                             server,
                                             self.server_feedback))
            s.start()
            time.sleep(1)

        c = Thread(target=wrapper, args=(self,
                                         client,
                                         self.client_feedback))
        c.start()
        client_error = self.client_feedback.get()

        if server is not None:
            os.write(self.pw, b'q')
            server_error = self.server_feedback.get()
            s.join()

        c.join()

        if any((client_error, server_error)):
            print("client error:")
            print(client_error)
            print("server error:")
            print(server_error)
            e = RuntimeError()
            e.client_error = client_error
            e.server_error = server_error
            raise e

    @skip_if_not_supported
    def test_create_bond(self):
        require_user('root')
        self.launcher('create_bond')

    def test_create_interface(self):
        require_user('root')
        self.launcher('create_interface')

    @skip_if_not_supported
    def test_create_vlan(self):
        require_user('root')
        self.launcher('create_vlan')

    def test_ip_monitor(self):
        require_user('root')
        self.launcher('interface_event', server='ip_monitor')

    @skip_if_not_supported
    def test_ipdb_autobr(self):
        require_user('root')
        self.launcher('ipdb_autobr')

    @skip_if_not_supported
    def test_ipdb_chain(self):
        require_user('root')
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

    def test_nl80211_interfaces(self):
        try:
            self.launcher('nl80211_interfaces')
        except Exception as x:
            if isinstance(x.client_error, NetlinkError) and \
                    x.client_error.code == errno.ENOENT:
                raise SkipTest('nl80211 not supported')
            else:
                raise

    def test_nl80211_interface_type(self):
        try:
            self.launcher('nl80211_interface_type')
        except Exception as x:
            if isinstance(x.client_error, NetlinkError) and \
                    x.client_error.code == errno.ENOENT:
                raise SkipTest('nl80211 not supported')
            else:
                raise

    def test_taskstats(self):
        require_user('root')
        try:
            self.launcher('taskstats')
        except Exception as x:
            if isinstance(x.client_error, NetlinkError) and \
                    x.client_error.code == errno.ENOENT:
                raise SkipTest('missing taskstats support')
            else:
                raise

    def _test_pmonitor(self):
        require_user('root')
        try:
            self.launcher('pmonitor', server='server')
        except Exception as x:
            if x.code == errno.ENOENT:
                raise SkipTest('missing taskstats support')
            else:
                raise
