###
#
# This example shows how to define and use a custom socket base
# class to be used with NetlinkSocket.
#
# socket_wrapper module overrides the SocketBase; only after
# that we should import IPRoute
#
# Override SocketBase
import types
from socket import socket
from functools import partial
from pyroute2 import config
from pyroute2 import IPRoute


###
#
# socket.socket isn't very subclass-friendly, so wrap it instead.
#
class SocketWrapper(object):
    def __init__(self, *args, **kwargs):
        _socketmethods = (
            'bind', 'close', 'connect', 'connect_ex', 'listen',
            'getpeername', 'getsockname', 'getsockopt', 'makefile',
            'recv', 'recvfrom', 'recv_into', 'recvfrom_into',
            'send', 'sendto', 'sendall', 'setsockopt', 'setblocking',
            'settimeout', 'gettimeout', 'shutdown')
        _sock = kwargs.get('_sock', None) or socket(*args, **kwargs)
        self._sock = _sock
        print("Custom socket wrapper init done")

        def _forward(name, self, *args, **kwargs):
            print("Forward <%s> method" % name)
            return getattr(self._sock, name)(*args, **kwargs)

        for name in _socketmethods:
            f = partial(_forward, name)
            f.__name__ = name
            setattr(SocketWrapper, name, types.MethodType(f, self))

    def fileno(self):
        # for some obscure reason, we can not implement `fileno()`
        # proxying as above, so just make a hardcore version
        return self._sock.fileno()

    def dup(self):
        return self.__class__(_sock=self._sock.dup())

config.SocketBase = SocketWrapper


###
#
# Being run via the root module, real IPRoute import is postponed,
# to inspect the code, refer to `pyroute2/__init__.py`
#
ip = IPRoute()
print(ip.get_addr())
ip.close()
