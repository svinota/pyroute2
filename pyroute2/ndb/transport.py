import time
import uuid
import socket
import pickle
import select
import struct


class Peer(object):

    def __init__(self, peer_id, address, port, proto):
        self.address = address
        self.port = port
        self.socket = None
        self.proto = proto
        self.peer_id = peer_id

    def __repr__(self):
        return '%s:%s' % (self.address, self.port)

    def send_as(self, data, peer_id):
        length = len(data)
        data = struct.pack('II', length, peer_id) + data
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, self.proto)
            if self.proto == socket.SOCK_STREAM:
                try:
                    self.socket.connect((self.address, self.port))
                except Exception:
                    self.socket = None
                    return
        try:
            if self.proto == socket.SOCK_DGRAM:
                self.socket.sendto(data, (self.address, self.port))
            elif self.proto == socket.SOCK_STREAM:
                self.socket.send(data)
        except Exception:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def close(self):
        self.socket.close()


class Transport(object):

    def __init__(self, peer_id, address, port, proto):
        self.peers = []
        self.peer_id = peer_id
        self.address = address
        self.port = port
        self.proto = proto
        self.socket = socket.socket(socket.AF_INET, self.proto)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.socket.bind((self.address, self.port))
        if self.proto == socket.SOCK_STREAM:
            self.socket.listen(16)
        self.stream_endpoints = []

    def add_peer(self, peer_id, address, port):
        peer = Peer(peer_id, address, port, self.proto)
        self.peers.append(peer)
        return peer

    def send(self, data, exclude=None):
        exclude = exclude or []
        ret = []
        for peer in self.peers:
            if peer.peer_id not in exclude:
                ret.append(peer.send_as(data, self.peer_id))
        return ret

    def get(self):
        if self.proto == socket.SOCK_DGRAM:
            data, _ = self.socket.recvfrom(8)
            length, peer_id = struct.unpack('II', data)
            data, _ = self.socket.recvfrom(length)
            return data, peer_id
        elif self.proto == socket.SOCK_STREAM:
            while True:
                fds = [self.socket] + self.stream_endpoints
                [rlist, wlist, xlist] = select.select(fds, [], fds)
                for fd in xlist:
                    if fd in self.stream_endpoints:
                        self.stream_endpoints.pop(fd)
                for fd in rlist:
                    if fd == self.socket:
                        new_fd, raddr = self.socket.accept()
                        self.stream_endpoints.append(new_fd)
                    else:
                        data = fd.recv(8)
                        length, peer_id = struct.unpack('II', data)
                        data = fd.recv(length)
                        return data, peer_id

    def close(self):
        self.socket.close()


class Messenger(object):

    def __init__(self, transport=None):
        self.transport = transport or \
            Transport('0.0.0.0', 5680, socket.SOCK_STREAM)
        self.targets = set()
        self.id_cache = {}

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            msg = self.handle()
            if msg is not None:
                return msg

    def handle(self):
        data, peer_id = self.transport.get()
        message = pickle.loads(data)

        if message['id'] in self.id_cache:
            # discard message
            return None

        if message['protocol'] == 'system':
            # forward system messages
            self.transport.send(data, exclude=[peer_id, ])
            return message

        self.id_cache[message['id']] = time.time()

        if message['target'] in self.targets:
            # forward message
            message = None
        self.transport.send(data, exclude=[peer_id, ])
        return message

    def emit(self, target, op, data):

        while True:
            message_id = '%s-%s' % (target, uuid.uuid4().hex)
            if message_id not in self.id_cache:
                self.id_cache[message_id] = time.time()
                break

        message = {'protocol': 'transport',
                   'target': target,
                   'id': message_id,
                   'op': op,
                   'data': data}

        return self.transport.send(pickle.dumps(message))

    def add_peer(self, peer_id, address, port):
        peer = self.transport.add_peer(peer_id, address, port)
        self.hello(peer)

    def hello(self, peer):
        while True:
            message_id = str(uuid.uuid4().hex)
            if message_id not in self.id_cache:
                self.id_cache[message_id] = time.time()
                break
        data = pickle.dumps({'protocol': 'system',
                             'id': message_id,
                             'data': 'HELLO'})
        peer.send_as(data, self.transport.peer_id)
