import time
import socket
import threading
import subprocess
from pyroute2 import Conntrack
from pyroute2 import NFCTSocket
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTAttrTuple


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


class TestDumpEntries(object):

    def add_tuple(self, saddr, daddr, proto, sport, dport):
        tuple_orig = NFCTAttrTuple(
            saddr=saddr, daddr=daddr, proto=proto, sport=sport, dport=dport)
        self.tuples.append(tuple_orig)
        return tuple_orig

    def setup(self):
        require_user('root')
        self.tuples = []
        self.COUNT_CT = 20
        self.ct = Conntrack()

        for sport in range(20000, 20000 + self.COUNT_CT):
            tuple_orig = self.add_tuple(
                saddr='192.168.122.1', daddr='192.168.122.67',
                proto=socket.IPPROTO_TCP, sport=sport, dport=5599)
            self.ct.entry('add', timeout=60,
                          tuple_orig=tuple_orig,
                          tuple_reply=tuple_orig.reverse())

    def test_dump(self):
        tuple_match = NFCTAttrTuple(saddr='192.168.122.1',
                                    daddr='192.168.122.67')

        count_found = 0
        tuple_filter = tuple_match
        for entry in self.ct.dump_entries(tuple_orig=tuple_match):
            count_found += 1
        assert count_found == self.COUNT_CT

        count_found = 0
        tuple_filter = NFCTAttrTuple(proto=socket.IPPROTO_TCP)
        for entry in self.ct.dump_entries(tuple_orig=tuple_filter):
            if tuple_match == entry.tuple_orig:
                count_found += 1

        assert count_found == self.COUNT_CT

    def teardown(self):
        for tuple_orig in self.tuples:
            self.ct.entry('del', tuple_orig=tuple_orig)
