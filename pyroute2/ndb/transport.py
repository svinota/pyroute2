import time
import uuid
import socket
import pickle


class Transport(object):

    def __init__(self, address, port):
        self.peers = set()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((address, port))

    def send(self, data, exclude=None):
        exclude = exclude or []
        ret = []
        for peer in self.peers:
            if peer not in exclude:
                ret.append(self.socket.sendto(data, peer))
        return ret

    def get(self):
        return self.socket.recvfrom(32000)

    def close(self):
        self.socket.close()


class Messenger(object):

    def __init__(self, transport=None):
        self.transport = transport or Transport('0.0.0.0', 5680)
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
        self.transport.peers.add((address, port))
        self.hello(address, port)

    def hello(self, address, port):
        while True:
            message_id = str(uuid.uuid4().hex)
            if message_id not in self.id_cache:
                self.id_cache[message_id] = time.time()
                break
        data = pickle.dumps({'protocol': 'system',
                             'id': message_id,
                             'data': 'HELLO'})
        self.transport.socket.sendto(data, (address, port))
