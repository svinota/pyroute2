import socket

from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.plan9 import Marshal9P


class Plan9Socket(NetlinkSocket):
    def __init__(self, *argv, **kwarg):
        kw = {}
        co_varnames = super().__init__.__code__.co_varnames
        for key, value in kwarg.items():
            if key in co_varnames:
                kw[key] = value
        super().__init__(**kw)
        self.marshal = Marshal9P()
        self.spec['tag_field'] = 'tag'

    def restart_base_socket(self, sock=None):
        if self.status['use_socket']:
            return self.use_socket
        sock = self.socket if sock is None else sock
        if sock is not None:
            sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def bind(self, *argv, **kwarg):
        return self.socket.bind(*argv, **kwarg)

    def accept(self):
        if self.status['use_socket']:
            return (self, None)
        (connection, address) = self.socket.accept()
        new_socket = self.clone()
        new_socket.socket = connection
        return (new_socket, address)

    def connect(self, address):
        self.socket.connect(address)
