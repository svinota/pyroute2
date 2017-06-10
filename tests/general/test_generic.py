import os
from netl import Rlink  # examples/generic/netl.py
from netl import rcmd
from utils import require_user
from pyroute2 import NetlinkError
from nose.plugins.skip import SkipTest


class TestGeneric(object):

    def setup(self):
        require_user('root')
        # build the kernel module
        self.cwd = os.getcwd()
        os.chdir('examples/generic')
        os.system('make >/dev/null 2>&1')
        os.system('rmmod netl >/dev/null 2>&1')
        os.system('insmod netl.ko')
        self.rlink = Rlink()
        try:
            self.rlink.bind('EXMPL_GENL', rcmd)
        except NetlinkError:
            raise SkipTest('module not loaded')

    def test_nla_length(self):
        assert self.rlink.send_data('x' * 65000) == 65000

    def teardown(self):
        self.rlink.close()
        os.system('rmmod netl')
        os.system('make clean >/dev/null 2>&1')
        os.chdir(self.cwd)
