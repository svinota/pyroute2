import socket
import threading
from pyroute2.iproute import IPRoute
try:
    from Queue import Queue
except ImportError:
    from queue import Queue


class Client(IPRoute):

    def __init__(self, addr):
        IPRoute.__init__(self)
        self.proxy = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.proxy.bind(('0.0.0.0', 3547))
        self.proxy_addr = addr
        self.proxy_queue = Queue()

        def recv():
            while True:
                (data, addr) = self.proxy.recvfrom(16384)
                self.proxy_queue.put(data)

        self.pthread = threading.Thread(target=recv)
        self.pthread.setDaemon(True)
        self.pthread.start()

        def sendto(buf, *argv, **kwarg):
            return self.proxy.sendto(buf, (self.proxy_addr, 3546))

        def recv(*argv, **kwarg):
            return self.proxy_queue.get()
        
        self._sendto = sendto
        self._recv = recv
