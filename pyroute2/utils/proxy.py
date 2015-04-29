import select
import socket
import struct
from pyroute2 import IPRoute


class Server(object):

    def __init__(self, addr='0.0.0.0', port=3546):
        self.addr = addr
        self.port = port

    def run(self):
        nat = {}
        clients = []

        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind((self.addr, self.port))
        ipr = IPRoute()
        ipr.bind()

        poll = select.poll()
        poll.register(ipr, select.POLLIN | select.POLLPRI)
        poll.register(srv, select.POLLIN | select.POLLPRI)

        while True:
            events = poll.poll()
            for (fd, event) in events:
                if fd == ipr.fileno():
                    bufsize = ipr.getsockopt(socket.SOL_SOCKET,
                                             socket.SO_RCVBUF) // 2
                    data = ipr.recv(bufsize)
                    cookie = struct.unpack('I', data[8:12])[0]
                    if cookie == 0:
                        for address in clients:
                            srv.sendto(data, address)
                    else:
                        srv.sendto(data, nat[cookie])
                else:
                    data, address = srv.recvfrom(16384)
                    if data is None:
                        clients.remove(address)
                        continue
                    cookie = struct.unpack('I', data[8:12])[0]
                    nat[cookie] = address
                    ipr.sendto(data, (0, 0))
