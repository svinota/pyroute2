import time
import socket
import pickle
from pyroute2.common import uuid32


class Transport(object):

    def __init__(self, address, port):
        self.neighbours = set()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((address, port))

    def send(self, data, exclude=None):
        exclude = exclude or []
        ret = []
        print('exclude', exclude)
        for neighbour in self.neighbours:
            print('neighbour', neighbour)
            if neighbour not in exclude:
                ret.append(self.socket.sendto(data, neighbour))
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
        print('source', address)
        message = pickle.loads(data)

        if message['protocol'] == 'system':
            print('control plane')
            return message

        if message['id'] in self.id_cache:
            # discard message
            print('discard message', message)
            return None

        if message['target'] not in self.targets:
            # handle message with a local target
            print('landing message', message)
            return message

        else:
            # forward message
            print('forward message', message)
            self.id_cache[message['id']] = time.time()
            self.transport.send(data, exclude=[address, ])
            return None

    def emit(self, target, op, data):

        while True:
            message_id = '%s-%s' % (target, uuid32())
            if message_id not in self.id_cache:
                self.id_cache[message_id] = time.time()
                break

        message = {'protocol': 'transport',
                   'target': target,
                   'id': message_id,
                   'op': op,
                   'data': data}

        return self.transport.send(pickle.dumps(message))

    def add_neighbour(self, address, port):
        self.transport.neighbours.add((address, port))
        self.hello(address, port)

    def hello(self, address, port):
        data = pickle.dumps({'protocol': 'system',
                             'data': 'HELLO'})
        self.transport.socket.sendto(data, (address, port))
