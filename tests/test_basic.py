import os
from pyroute2 import iproute
from pyroute2.netlink import IPRCMD_STOP
from multiprocessing import Event
from multiprocessing import Process


def _run_remote_uplink(url, allow_connect):
    ip = iproute()
    ip.iothread.allow_rctl = True
    ip.serve(url)
    allow_connect.set()
    ip.iothread._stop_event.wait()


def _assert_uplinks(ip, num):
    assert len(ip.get_sockets()) == num
    assert len(ip.iothread.uplinks) == num
    assert len(ip.iothread._rlist) >= num + 1


class TestSetup(object):

    def test_simple(self):
        ip = iproute()
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)

    def test_noautoconnect(self):
        ip = iproute(do_connect=False)
        _assert_uplinks(ip, 0)
        ip.connect()
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)


class TestUplinks(object):

    def _test_remote(self, url):
        allow_connect = Event()
        target = Process(target=_run_remote_uplink, args=(url, allow_connect))
        target.start()
        allow_connect.wait()
        ip = iproute(host=url)
        _assert_uplinks(ip, 1)
        # time.sleep(1)
        ip._remote_cmd(sock=tuple(ip._sockets)[0], cmd=IPRCMD_STOP)
        target.join()
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)

    def test_unix_abstract_remote(self):
        self._test_remote('unix://\0nose_tests_socket')

    def test_unix_remote(self):
        sck = './nose_tests_socket'
        url = 'unix://' + sck
        try:
            os.remove(sck)
        except OSError as e:
            if e.errno != 2:  # no such file or directory
                raise e
        self._test_remote(url)

    def test_tcp_remote(self):
        self._test_remote('tcp://127.0.0.1:9821')
