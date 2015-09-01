import atexit
import pickle
import select
import socket
import struct
import threading
import traceback
import urlparse
from io import BytesIO
from socket import SOL_SOCKET
from socket import SO_RCVBUF
from pyroute2 import IPRoute
from pyroute2.common import uuid32
from pyroute2.netlink.nlsocket import NetlinkMixin
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.iproute import IPRouteMixin


class Connection(object):
    def __init__(self, sock):
        self.sock = sock
        self.sock.setblocking(True)

    def fileno(self):
        return self.sock.fileno()

    def send(self, obj):
        dump = BytesIO()
        pickle.dump(obj, dump)
        packet = struct.pack("II", len(dump.getvalue()) + 8, 0)
        packet += dump.getvalue()
        self.sock.sendall(packet)

    def recv(self):
        length, offset = struct.unpack("II", self.sock.recv(8))
        dump = BytesIO()
        dump.write(self.sock.recv(length - 8))
        return pickle.load(dump)

    def close(self):
        self.sock.close()


class Channel(Connection):

    def __init__(self, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        Connection.__init__(self, sock)


def Server(cmdch, brdch):

    try:
        ipr = IPRoute()
        lock = ipr._sproxy.lock
        ipr._s_channel = brdch
        poll = select.poll()
        poll.register(ipr, select.POLLIN | select.POLLPRI)
        poll.register(cmdch, select.POLLIN | select.POLLPRI)
    except Exception as e:
        cmdch.send({'stage': 'init',
                    'error': e})
        return 255

    # all is OK so far
    cmdch.send({'stage': 'init',
                'error': None})
    # 8<-------------------------------------------------------------
    while True:
        events = poll.poll()
        for (fd, event) in events:
            if fd == ipr.fileno():
                bufsize = ipr.getsockopt(SOL_SOCKET, SO_RCVBUF) // 2
                with lock:
                    brdch.send({'stage': 'broadcast',
                                'data': ipr.recv(bufsize)})
            elif fd == cmdch.fileno():
                cmd = cmdch.recv()
                if cmd['stage'] == 'shutdown':
                    poll.unregister(ipr)
                    poll.unregister(cmdch)
                    ipr.close()
                    return
                elif cmd['stage'] == 'command':
                    error = None
                    try:
                        ret = getattr(ipr, cmd['name'])(*cmd['argv'],
                                                        **cmd['kwarg'])
                    except Exception as e:
                        error = e
                        error.tb = traceback.format_exc()
                    cmdch.send({'stage': 'command',
                                'error': error,
                                'return': ret,
                                'cookie': cmd['cookie']})


class Client(object):

    brdch = None
    cmdch = None

    def __init__(self):
        self.cmdlock = threading.Lock()
        self.lock = threading.Lock()
        self.closed = False
        init = self.cmdch.recv()
        if init['stage'] != 'init':
            raise TypeError('incorrect protocol init')
        if init['error'] is not None:
            raise init['error']
        else:
            atexit.register(self.close)

    def recv(self, bufsize, flags=0):
        return self.brdch.recv()['data']

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.cmdch.send({'stage': 'shutdown'})
                self.cmdch.close()
                self.brdch.close()

    def proxy(self, cmd, *argv, **kwarg):
        with self.cmdlock:
            self.cmdch.send({'stage': 'command',
                             'cookie': None,
                             'name': cmd,
                             'argv': argv,
                             'kwarg': kwarg})
            ret = self.cmdch.recv()
            if ret['error'] is not None:
                raise ret['error']
            return ret['return']

    def fileno(self):
        return self.brdch.fileno()

    def bind(self, *argv, **kwarg):
        if 'async' in kwarg:
            # do not work with async servers
            kwarg['async'] = False
        return self.proxy('bind', *argv, **kwarg)

    def send(self, *argv, **kwarg):
        return self.proxy('send', *argv, **kwarg)

    def sendto(self, *argv, **kwarg):
        return self.proxy('sendto', *argv, **kwarg)

    def getsockopt(self, *argv, **kwarg):
        return self.proxy('getsockopt', *argv, **kwarg)

    def setsockopt(self, *argv, **kwarg):
        return self.proxy('setsockopt', *argv, **kwarg)


class RemoteSocket(NetlinkMixin, Client):

    def bind(self, *argv, **kwarg):
        return Client.bind(self, *argv, **kwarg)

    def close(self):
        Client.close(self)

    def _sendto(self, *argv, **kwarg):
        return Client.sendto(self, *argv, **kwarg)

    def _recv(self, *argv, **kwarg):
        return Client.recv(self, *argv, **kwarg)


class Remote(IPRouteMixin, RemoteSocket):
    def __init__(self, url):
        if url.startswith('tcp://'):
            hostname = urlparse.urlparse(url).netloc
            self.cmdch = Channel(hostname, 4336)
            self.brdch = Channel(hostname, 4336)
            self.uuid = uuid32()
            self.cmdch.send({'stage': 'init',
                             'domain': 'command',
                             'client': self.uuid})
            self.brdch.send({'stage': 'init',
                             'domain': 'broadcast',
                             'client': self.uuid})
        else:
            raise TypeError('remote connection type not supported')
        super(RemoteSocket, self).__init__()
        self.marshal = MarshalRtnl()

    def post_init(self):
        pass


class Master(object):

    def __init__(self, host='localhost', port=4336):
        self.master_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.master_sock.bind((host, port))
        self.new = {}
        self.clients = {}
        self.threads = []

    def start(self):
        self.master_sock.listen(4)

        poll = select.poll()
        poll.register(self.master_sock, select.POLLIN | select.POLLPRI)
        while True:
            for (fd, event) in poll.poll():
                if fd == self.master_sock.fileno():
                    (sock, info) = self.master_sock.accept()
                    self.new[sock.fileno()] = Connection(sock)
                    poll.register(sock, select.POLLIN | select.POLLPRI)
                elif fd in self.new:
                    init = self.new[fd].recv()
                    if init['client'] in self.clients:
                        client = self.clients.pop(init['client'])
                        client[init['domain']] = self.new.pop(fd)
                        args = (client['command'],
                                client['broadcast'])
                        t = threading.Thread(target=Server, args=args)
                        t.start()
                        self.threads.append(t)
                        poll.unregister(client['command'].sock)
                        poll.unregister(client['broadcast'].sock)
                    else:
                        cid = init['client']
                        self.clients[cid] = {}
                        self.clients[cid][init['domain']] = self.new.pop(fd)
                else:
                    raise Exception('lost socket fd')
