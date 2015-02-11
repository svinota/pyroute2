import sys
import select
from pyroute2 import IPRoute
from socket import socket
from socket import AF_INET
from socket import SOCK_STREAM
from socket import SOL_SOCKET
from socket import SO_REUSEADDR

ip = IPRoute()

##
#
pr = socket(AF_INET, SOCK_STREAM)
pr.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
pr.bind(('127.0.0.1', 4011))
pr.listen(1)
(client, addr) = pr.accept()
ip._s_channel = client

##
#
poll = select.poll()
poll.register(client, select.POLLIN | select.POLLPRI)
poll.register(ip, select.POLLIN | select.POLLPRI)

while True:
    events = poll.poll()
    for (fd, event) in events:
        if fd == client.fileno():
            try:
                ip.sendto(client.recv(16384), (0, 0))
            except:
                sys.exit(0)
        else:
            client.send(ip.recv(16384))
