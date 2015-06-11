import socket
import multiprocessing
from pyroute2.config.capabilities import Capabilities

SocketBase = socket.socket
MpPipe = multiprocessing.Pipe
MpQueue = multiprocessing.Queue
MpProcess = multiprocessing.Process

commit_barrier = 0

capabilities = Capabilities()
