import select
import socket
import struct
from pyroute2 import IPRoute

nat = {}
clients = []

srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
srv.bind(('0.0.0.0', 3546))
ipr = IPRoute()
ipr.bind()

poll = select.poll()
poll.register(ipr, select.POLLIN | select.POLLPRI)
poll.register(srv, select.POLLIN | select.POLLPRI)

while True:
    events = poll.poll()
    for (fd, event) in events:
        if fd == ipr.fileno():
            bufsize = ipr.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF) // 2
            data = ipr.recv(bufsize)
            cookie = struct.unpack('I', data[8:12])[0]
            if cookie == 0:
                for address in clients:
                    srv.sendto(data, (address, 3547))
            else:
                srv.sendto(data, (nat[cookie], 3547))
        else:
            data, (address, port) = srv.recvfrom(16384)
            if data is None:
                clients.remove(address)
                continue
            cookie = struct.unpack('I', data[8:12])[0]
            nat[cookie] = address
            ipr.sendto(data, (0, 0))
