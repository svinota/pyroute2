import socket

from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.plan9 import Marshal9P


class Plan9Socket(NetlinkSocket):
    def __init__(self, *argv, **kwarg):
        super().__init__()
        self.marshal = Marshal9P()

    def restart_base_socket(self, sock=None):
        sock = self.socket if sock is None else sock
        if sock is not None:
            sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def bind(self, *argv, **kwarg):
        return self.socket.bind(*argv, **kwarg)

    def accept(self):
        (connection, address) = self.socket.accept()
        new_socket = self.clone()
        new_socket.socket = connection
        return (new_socket, address)
