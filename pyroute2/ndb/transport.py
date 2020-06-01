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
        for neighbour in self.neighbours:
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

    def handle(self):
        data, address = self.transport.get()
        message = pickle.loads(data)

        if message['id'] in self.id_cache:
            # discard message
            print('discard message', message)
            return None

        if message['target'] in self.targets:
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

        message = {'target': target,
                   'id': message_id,
                   'op': op,
                   'data': data}

        return self.transport.send(pickle.dumps(message))
