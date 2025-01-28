import json
import socket
import sys

from pyroute2 import netns


def main(nsname, ctrl, flags, family, socket_type, proto):
    try:
        netns.setns(nsname, flags=flags)
        sock = socket.socket(family, socket_type, proto)
        payload = {}
        fds = [sock.fileno()]
    except Exception as e:
        payload = {'name': e.__class__.__name__, 'args': e.args}
        fds = []
    finally:
        socket.send_fds(ctrl, [json.dumps(payload).encode('utf-8')], fds, 1)


if __name__ == '__main__':
    nsname = sys.argv[1]
    fd, flags, family, socket_type, proto = [int(x) for x in sys.argv[2:]]
    ctrl = socket.socket(fileno=fd)
    main(nsname, ctrl, flags, family, socket_type, proto)
