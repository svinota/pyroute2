import re
import socket
import time

from pyroute2 import NDB
from pyroute2.ndb.main import MetricsHTTPConfig


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _fetch_metrics(port):
    with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
        sock.sendall(
            b'GET /metrics HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n'
        )
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b''.join(chunks).decode()


def test_prometheus_text():
    port = _free_port()
    with NDB(metrics_config=MetricsHTTPConfig(port=port)):
        body = None
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                body = _fetch_metrics(port)
                if 'HTTP/1.1 200 OK' in body:
                    break
            except OSError:
                time.sleep(0.05)
        assert body is not None
        assert 'HTTP/1.1 200 OK' in body
        assert '# TYPE pyroute2_ndb_process_rss_bytes gauge' in body
        rss_match = re.search(r'pyroute2_ndb_process_rss_bytes\s+(\d+)', body)
        assert rss_match is not None
        assert int(rss_match.group(1)) > 0
