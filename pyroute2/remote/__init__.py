import os
import atexit
import pickle
import select
import signal
import socket
import struct
import threading
import traceback
from io import BytesIO
from socket import SOL_SOCKET
from socket import SO_RCVBUF
from pyroute2 import IPRoute
from pyroute2.common import uuid32
from pyroute2.netlink.nlsocket import NetlinkMixin
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.iproute import IPRouteMixin
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


class Transport(object):
    '''
    A simple transport protocols to send objects between two
    end-points. Requires an open socket-like object at init.
    '''
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
        actual = 0
        while actual < (length - 8):
            chunk = self.sock.recv(length - 8 - actual)
            actual += len(chunk)
            dump.write(chunk)
        dump.seek(0)
        ret = pickle.load(dump)
        return ret

    def close(self):
        self.sock.close()


class SocketChannel(Transport):
    '''
    A data channel over ordinary AF_INET socket.
    '''

    def __init__(self, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        Transport.__init__(self, sock)


class ProxyChannel(object):

    def __init__(self, channel, stage):
        self.target = channel
        self.stage = stage

    def send(self, data):
        return self.target.send({'stage': self.stage,
                                 'data': data,
                                 'error': None})


def Server(cmdch, brdch):
    '''
    A server routine to run an IPRoute object and expose it via
    custom RPC.

    many TODOs:

    * document the protocol
    * provide not only IPRoute

    RPC

    Messages sent via channels are dictionaries with predefined
    structure. There are 4 s.c. stages::

        init        (server <-----> client)
        command     (server <-----> client)
        broadcast   (server ------> client)
        shutdown    (server <------ client)


    Stage 'init' is used during initialization. The client
    establishes connections to the server and announces them
    by sending a single message via each channel::

        {'stage': 'init',
         'domain': ch_domain,
         'client': client.uuid}

    Here, the client uuid is used to group all the connections
    of the same client and `ch_domain` is either 'command', or
    'broadcast'. The latter will become a unidirectional
    channel from the server to the client, all data that
    arrives on the server side via netlink socket will be
    forwarded to the broadcast channel.

    The command channel will be used to make RPC calls and
    to shut the worker thread down before the client
    disconnects from the server.

    When all the registration is done, the server sends a
    single message via the command channel::

        {'stage': 'init',
         'error': exception or None}

    If the `error` field is None, everything is ok. If it
    is an exception, the init is failed and the exception
    should be thrown on the client side.

    In the runtime, all the data that arrives on the netlink
    socket fd, is to be forwarded directly via the
    broadcast channel.

    Commands are handled with the `command` stage::

        # request

        {'stage': 'command',
         'name': str,
         'cookie': cookie,
         'argv': [...],
         'kwarg': {...}}

        # response

        {'stage': 'command',
         'error': exception or None,
         'return': retval,
         'cookie': cookie}

    Right now the protocol is synchronous, so there is not
    need in cookie yet. But in some future it can turn into
    async, and then cookies will be used to match messages.

    The final stage is 'shutdown'. It terminates the worker
    thread, has no response and no messages can passed after.

    '''

    def close(s, frame):
        # just leave everything else as is
        brdch.send({'stage': 'signal',
                    'data': s})

    try:
        ipr = IPRoute()
        lock = ipr._sproxy.lock
        ipr._s_channel = ProxyChannel(brdch, 'broadcast')
    except Exception as e:
        cmdch.send({'stage': 'init',
                    'error': e})
        return 255

    inputs = [ipr.fileno(), cmdch.fileno()]
    outputs = []

    # all is OK so far
    cmdch.send({'stage': 'init',
                'error': None})
    signal.signal(signal.SIGHUP, close)
    signal.signal(signal.SIGINT, close)
    signal.signal(signal.SIGTERM, close)

    # 8<-------------------------------------------------------------
    while True:
        try:
            events, _, _ = select.select(inputs, outputs, inputs)
        except:
            continue
        for fd in events:
            if fd == ipr.fileno():
                bufsize = ipr.getsockopt(SOL_SOCKET, SO_RCVBUF) // 2
                with lock:
                    error = None
                    data = None
                    try:
                        data = ipr.recv(bufsize)
                    except Exception as e:
                        error = e
                        error.tb = traceback.format_exc()
                    brdch.send({'stage': 'broadcast',
                                'data': data,
                                'error': error})
            elif fd == cmdch.fileno():
                cmd = cmdch.recv()
                if cmd['stage'] == 'shutdown':
                    ipr.close()
                    return
                elif cmd['stage'] == 'reconstruct':
                    error = None
                    try:
                        msg = cmd['argv'][0]()
                        msg.load(pickle.loads(cmd['argv'][1]))
                        msg.encode()
                        ipr.sendto_gate(msg, cmd['argv'][2])
                    except Exception as e:
                        error = e
                        error.tb = traceback.format_exc()
                    cmdch.send({'stage': 'reconstruct',
                                'error': error,
                                'return': None,
                                'cookie': cmd['cookie']})

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
        self.sendto_gate = self._gate

    def _gate(self, msg, addr):
        with self.cmdlock:
            self.cmdch.send({'stage': 'reconstruct',
                             'cookie': None,
                             'name': None,
                             'argv': [type(msg),
                                      pickle.dumps(msg.dump()),
                                      addr],
                             'kwarg': None})
            ret = self.cmdch.recv()
            if ret['error'] is not None:
                raise ret['error']
            return ret['return']

    def recv(self, bufsize, flags=0):
        msg = None
        while True:
            msg = self.brdch.recv()
            if msg['stage'] == 'signal':
                os.kill(os.getpid(), msg['data'])
            else:
                break
        if msg['error'] is not None:
            raise msg['error']
        return msg['data']

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.cmdch.send({'stage': 'shutdown'})
                if hasattr(self.cmdch, 'close'):
                    self.cmdch.close()
                if hasattr(self.brdch, 'close'):
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
        NetlinkMixin.close(self)
        Client.close(self)

    def _sendto(self, *argv, **kwarg):
        return Client.sendto(self, *argv, **kwarg)

    def _recv(self, *argv, **kwarg):
        return Client.recv(self, *argv, **kwarg)


class Remote(IPRouteMixin, RemoteSocket):
    '''
    Experimental TCP server.

    Only for debug purposes now.
    '''
    def __init__(self, url):
        if url.startswith('tcp://'):
            hostname = urlparse(url).netloc
            self.cmdch = SocketChannel(hostname, 4336)
            self.brdch = SocketChannel(hostname, 4336)
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
                    self.new[sock.fileno()] = Transport(sock)
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
