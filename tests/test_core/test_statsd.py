import shutil
import socket
import subprocess
import time
from collections import deque

import pytest

from pyroute2 import IPRoute, config
from pyroute2.common import uifname
from pyroute2.statsd import StatsDClientSocket

PORT_UDP = 8234
PORT_TCP = 8235


class StatsDServer:
    def __init__(self, tmp_path):
        config = tmp_path / 'statsd.json'
        config.write_text(f'{{"port": {PORT_UDP}, "mgmt_port": {PORT_TCP}}}')
        statsd = shutil.which('statsd')
        if statsd is None:
            return pytest.skip('statsd not found')
        self.server = subprocess.Popen(
            [statsd, config.as_posix()],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.query('counters')

    def try_query(self, kind: str) -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', PORT_TCP))
            s.send(f'{kind}\n'.encode())

            response = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                data = data.decode('utf-8')
                response.append(data)
                if 'END' in data:
                    break

            return ''.join(response)

    def query(self, kind: str) -> str:
        start_time = time.time()
        timeout = 5
        interval = 0.2

        while True:
            try:
                return self.try_query(kind)
            except (socket.error, socket.timeout):
                if time.time() - start_time > timeout:
                    raise RuntimeError('statsd server unreachable')
                time.sleep(interval)

    def get(self, kind: str, name: str) -> int:
        d = deque(self.query(kind).split())
        while True:
            token = d.popleft()
            if token == f'{name}:':
                return int(d.popleft())
        raise KeyError('metric not found')

    def close(self):
        self.server.terminate()
        self.server.kill()


@pytest.fixture
def statsd(tmp_path):
    sd = StatsDServer(tmp_path)
    yield sd
    sd.close()


@pytest.mark.parametrize(
    'kind,func,ret',
    (
        ('counters', lambda x, n: x.incr(n), 1),
        ('gauges', lambda x, n: x.gauge(n, 10), 10),
    ),
)
def test_call(statsd, kind, func, ret):
    with StatsDClientSocket(address=('localhost', PORT_UDP)) as sc:
        metric = uifname()
        func(sc, metric)
        assert statsd.get(kind, metric) == ret


def test_telemetry(statsd, monkeypatch):
    monkeypatch.setattr(config, 'telemetry', ('localhost', PORT_UDP))
    with IPRoute() as ipr:
        assert len(list(ipr.link_lookup(ifname='lo'))) == 1
    assert (
        len(
            list(
                filter(
                    lambda x: x == 'link_lookup:',
                    statsd.query('counters').split(),
                )
            )
        )
        > 0
    )
