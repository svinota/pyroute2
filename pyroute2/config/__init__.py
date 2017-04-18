import os
import socket
import platform
import multiprocessing
from pyroute2 import common
from distutils.version import LooseVersion

TransactionalBase = common.Dotkeys
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

# IFLA_INFO_DATA plugin system prototype
_absdir = os.path.dirname(os.path.abspath(common.__file__))
data_plugins_path = [_absdir + '/netlink/rtnl/ifinfmsg/plugins', ]
