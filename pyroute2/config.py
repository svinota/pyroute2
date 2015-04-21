import socket
import multiprocessing

SocketBase = socket.socket
MpPipe = multiprocessing.Pipe
MpQueue = multiprocessing.Queue
MpProcess = multiprocessing.Process

commit_barrier = 0.2
