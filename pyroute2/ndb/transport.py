import time
import uuid
import socket
import pickle
import select
import struct


class IdCache(dict):

    def invalidate(self):
        current_time = time.time()
        collect_time = current_time - 60
        for mid, meta in tuple(self.items()):
            if meta < collect_time:
                self.pop(mid)

    def __setitem__(self, key, value):
        if len(self) > 100:
            self.invalidate()
        dict.__setitem__(self, key, value)


class Peer(object):

    def __init__(self, remote_id, local_id, address, port, proto, cache):
        self.address = address
        self.port = port
        self.socket = None
        self.proto = proto
        self.remote_id = remote_id
        self.local_id = local_id
        self.cache = cache
        self.last_exception_time = 0

    def __repr__(self):
        return '[%s-%s] %s:%s' % (self.local_id,
                                  self.remote_id,
                                  self.address,
                                  self.port)

    def hello(self):
        while True:
            message_id = str(uuid.uuid4().hex)
            if message_id not in self.cache:
                self.cache[message_id] = time.time()
                break
        data = pickle.dumps({'protocol': 'system',
                             'id': message_id,
                             'data': 'HELLO'})
        self.send(data)

    def send(self, data):
        length = len(data)
        data = struct.pack('II', length, self.local_id) + data
        if self.socket is None:
            if time.time() - self.last_exception_time < 5:
                return
            self.socket = socket.socket(socket.AF_INET, self.proto)
            if self.proto == socket.SOCK_STREAM:
                try:
                    self.socket.connect((self.address, self.port))
                    self.hello()
                except Exception:
                    self.last_exception_time = time.time()
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

    def __init__(self, address, port, proto):
        self.peers = []
        self.address = address
        self.port = port
        self.proto = proto
        self.socket = socket.socket(socket.AF_INET, self.proto)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.address, self.port))
        if self.proto == socket.SOCK_STREAM:
            self.socket.listen(16)
        self.stream_endpoints = []

    def add_peer(self, peer):
        self.peers.append(peer)

    def send(self, data, exclude=None):
        exclude = exclude or []
        ret = []
        for peer in self.peers:
            if peer.remote_id not in exclude:
                ret.append(peer.send(data))
        return ret

    def get(self):
        if self.proto == socket.SOCK_DGRAM:
            data, _ = self.socket.recvfrom(8)
            length, remote_id = struct.unpack('II', data)
            data, _ = self.socket.recvfrom(length)
            return data, remote_id
        elif self.proto == socket.SOCK_STREAM:
            while True:
                fds = [self.socket] + self.stream_endpoints
                [rlist, wlist, xlist] = select.select(fds, [], fds)
                for fd in xlist:
                    if fd in self.stream_endpoints:
                        (self
                         .stream_endpoints
                         .pop(self
                              .stream_endpoints
                              .index(fd)))
                for fd in rlist:
                    if fd == self.socket:
                        new_fd, raddr = self.socket.accept()
                        self.stream_endpoints.append(new_fd)
                    else:
                        data = fd.recv(8)
                        if len(data) == 0:
                            (self
                             .stream_endpoints
                             .pop(self
                                  .stream_endpoints
                                  .index(fd)))
                            continue
                        length, remote_id = struct.unpack('II', data)
                        data = b''
                        while len(data) < length:
                            data += fd.recv(length - len(data))
                        return data, remote_id

    def close(self):
        self.socket.close()


class Messenger(object):

    def __init__(self, local_id, transport=None):
        self.local_id = local_id
        self.transport = transport or \
            Transport('0.0.0.0', 5680, socket.SOCK_STREAM)
        self.targets = set()
        self.id_cache = IdCache()

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            msg = self.handle()
            if msg is not None:
                return msg

    def handle(self):
        data, remote_id = self.transport.get()
        message = pickle.loads(data)

        if message['id'] in self.id_cache:
            # discard message
            return None

        if message['protocol'] == 'system':
            # forward system messages
            self.transport.send(data, exclude=[remote_id, ])
            return message

        self.id_cache[message['id']] = time.time()

        if message['target'] in self.targets:
            # forward message
            message = None
        self.transport.send(data, exclude=[remote_id, ])
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

    def add_peer(self, remote_id, address, port):
        peer = Peer(remote_id,
                    self.local_id,
                    address,
                    port,
                    self.transport.proto,
                    self.id_cache)
        self.transport.add_peer(peer)
