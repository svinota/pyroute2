
from pyroute2 import config

if config.uname[0] == 'FreeBSD':
    from pyroute2.bsd.rtmsocket.freebsd import RTMSocket
elif config.uname[0] == 'OpenBSD':
    from pyroute2.bsd.rtmsocket.openbsd import RTMSocket
else:
    raise ImportError('platform not supported')

__all__ = [RTMSocket, ]
