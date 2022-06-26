import os
import socket
import struct

from netl import Rlink  # examples/generic/netl.py
from netl import rcmd
from nose.plugins.skip import SkipTest
from utils import require_user

from pyroute2 import NetlinkError

_cwd = None


def setup_module():
    global _cwd
    require_user('root')
    # build the kernel module
    _cwd = os.getcwd()
    os.chdir('examples/generic')
    os.system('make >/dev/null 2>&1')
    os.system('rmmod netl >/dev/null 2>&1')
    os.system('insmod netl.ko')


def teardown_module():
    global _cwd
    os.system('rmmod netl')
    os.system('make clean >/dev/null 2>&1')
    os.chdir(_cwd)


class TestGeneric(object):
    def setup(self):
        require_user('root')
        self.rlink = Rlink()
        try:
            self.rlink.bind('EXMPL_GENL', rcmd)
        except NetlinkError:
            raise SkipTest('module not loaded')

    def test_nla_length(self):
        assert self.rlink.send_data('x' * 65000) == 65000

    def test_nla_length_exceeds_send(self):
        try:
            self.rlink.send_data('x' * 65530)
        except socket.error as e:
            if e.errno == 90:
                return
            raise

    def test_nla_length_exceeds_pack(self):
        try:
            self.rlink.send_data('x' * 66000)
        except struct.error:
            pass

    def teardown(self):
        self.rlink.close()
