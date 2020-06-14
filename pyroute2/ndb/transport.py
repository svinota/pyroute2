import time
import uuid
import socket
import pickle


class Peer(object):

    def __init__(self, address, port, proto):
        self.address = address
        self.port = port
        self.socket = None
        self.proto = proto

    def send(self, data):
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

    def __init__(self, address, port, proto):
        self.peers = []
        self.address = address
        self.port = port
        self.proto = proto
        self.socket = socket.socket(socket.AF_INET, self.proto)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.socket.bind((self.address, self.port))

    def add_peer(self, address, port):
        peer = Peer(address, port, self.proto)
        self.peers.append(peer)
        return peer

    def send(self, data, exclude=None):
        exclude = exclude or []
        ret = []
        for peer in self.peers:
            if (peer.address, peer.port) not in exclude:
                ret.append(peer.send(data))
        return ret

    def get(self):
        if self.proto == socket.SOCK_DGRAM:
            return self.socket.recvfrom(32000)

    def close(self):
        self.socket.close()


class Messenger(object):

    def __init__(self, transport=None):
        self.transport = transport or \
            Transport('0.0.0.0', 5680, socket.SOCK_DGRAM)
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
        data, address = self.transport.get()
        message = pickle.loads(data)

        if message['id'] in self.id_cache:
            # discard message
            return None

        if message['protocol'] == 'system':
            # forward system messages
            self.transport.send(data, exclude=[address, ])
            return message

        self.id_cache[message['id']] = time.time()
        self.transport.send(data, exclude=[address, ])

        if message['target'] not in self.targets:
            # handle message from remote targets
            return message
        else:
            # forward message
            return None

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

    def add_peer(self, address, port):
        peer = self.transport.add_peer(address, port)
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
        peer.send(data)
