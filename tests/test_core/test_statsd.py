import shutil
import socket
import subprocess
import time
from collections import deque

import pytest

from pyroute2.common import uifname
from pyroute2.statsd import StatsDSocket


class StatsDServer:
    def __init__(self, tmp_path):
        config = tmp_path / 'statsd.json'
        config.write_text('{}')
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
            s.connect(('localhost', 8126))
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
    with StatsDSocket(address=('localhost', 8125)) as sc:
        metric = uifname()
        func(sc, metric)
        assert statsd.get(kind, metric) == ret
