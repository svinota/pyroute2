import socket
import platform
import multiprocessing
from distutils.version import LooseVersion

SocketBase = socket.socket
MpPipe = multiprocessing.Pipe
MpQueue = multiprocessing.Queue
MpProcess = multiprocessing.Process
ipdb_nl_async = True

commit_barrier = 0

# save uname() on startup time: it is not so
# highly possible that the kernel will be
# changed in runtime, while calling uname()
# every time is a bit expensive
uname = platform.uname()
machine = platform.machine()
arch = platform.architecture()[0]
kernel = LooseVersion(uname[2]).version[:3]

AF_BRIDGE = getattr(socket, 'AF_BRIDGE', 7)
AF_NETLINK = getattr(socket, 'AF_NETLINK', 16)

data_plugins_pkgs = []
data_plugins_path = []
