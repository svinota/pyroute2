###
#
# The `socket.socket` class is not sublcass-friendly, and sometimes it is
# better to use a custom wrapper providing socket API, than the original
# socket class.
#
# But some projects, that use pyroute2, already have their own solutions,
# and providing the library-wide wrapper breaks the behaviour of these
# projects.
#
# So we provide a way to define a custom `SocketBase` class, that will be
# used as base for the `NetlinkSocket`
#
import types
from socket import socket
from functools import partial
from pyroute2 import config
from pyroute2 import netns
from pyroute2 import NetNS


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

print(netns.listnetns())
###
#
# Being run via the root module, real IPRoute import is postponed,
# to inspect the code, refer to `pyroute2/__init__.py`
#
ns = NetNS('test')
print(ns.get_addr())
ns.close()
