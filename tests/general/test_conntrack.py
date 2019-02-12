import time
import socket
import threading
import subprocess
from pyroute2 import Conntrack
from pyroute2 import NFCTSocket
from nose.plugins.skip import SkipTest
from utils import require_user


def server(address, port, env):
    ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ss.bind((address, port))
    ss.listen(1)
    conn, cadd = ss.accept()
    env['client'] = cadd
    conn.recv(16)
    conn.shutdown(socket.SHUT_RDWR)
    conn.close()
    ss.close()


class Client(object):

    def __init__(self, address, port):
        self.ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ss.connect((address, port))

    def stop(self):
        self.ss.send('\x00' * 16)
        self.ss.shutdown(socket.SHUT_RDWR)
        self.ss.close()


class BasicSetup(object):

    def setup(self):
        require_user('root')

        # run server / client
        self.env = {}
        self.ct = Conntrack()
        self.nfct = NFCTSocket()
        if self.ct.count() == 0:
            self.ct.close()
            self.nfct.close()
            raise SkipTest('conntrack modules are not supported')
        self.server = threading.Thread(target=server,
                                       args=('127.0.0.1', 5591, self.env))
        self.server.start()
        e = None
        for x in range(5):
            try:
                self.client = Client('127.0.0.1', 5591)
                time.sleep(1)
                break
            except Exception as exc:
                e = exc
        else:
            raise e

    def teardown(self):
        self.nfct.close()
        self.ct.close()
        self.client.stop()
        self.server.join()
        self.env = {}


class TestConntrack(BasicSetup):
    """ High level API tests
    """

    def test_stat(self):
        stat = self.ct.stat()
        cpus = [x for x in (subprocess
                            .check_output('cat /proc/cpuinfo', shell=True)
                            .split('\n')) if x.startswith('processor')]
        assert len(stat) == len(cpus)

    def test_count_dump(self):
        # These values should be pretty the same, but the call is not atomic
        # so some sessions may end or begin that time. Thus the difference
        # may occur, but should not be significant.
        assert abs(len(self.ct.dump()) - self.ct.count()) < 3


class TestNFCTSocket(BasicSetup):
    """ Low level API tests
    """

    def test_dump(self):
        # "grep" our client / server connection from the dump
        for connection in self.nfct.dump():
            addr = (connection
                    .get_attr('CTA_TUPLE_ORIG')
                    .get_attr('CTA_TUPLE_IP')
                    .get_attr('CTA_IP_V4_SRC'))
            port = (connection
                    .get_attr('CTA_TUPLE_ORIG')
                    .get_attr('CTA_TUPLE_PROTO')
                    .get_attr('CTA_PROTO_SRC_PORT'))
            if self.env['client'] == (addr, port):
                break
        else:
            raise Exception('connection not found')
