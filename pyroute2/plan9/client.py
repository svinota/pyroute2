import json
import os
import pwd
import socket

from pyroute2.common import AddrPool
from pyroute2.plan9 import (
    msg_tattach,
    msg_tcall,
    msg_tread,
    msg_tversion,
    msg_twalk,
    msg_twrite,
)
from pyroute2.plan9.plan9socket import Plan9Socket


class Plan9Client:
    def __init__(self, address=None, use_socket=None):
        if use_socket is None:
            use_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket = Plan9Socket(use_socket=use_socket)
        if address is not None:
            self.socket.connect(address)
        self.wnames = {'': 0}
        self.cwd = 0
        self.fid_pool = AddrPool(minaddr=0x00000001, maxaddr=0x0000FFFF)

    def init(self):
        self.version()
        self.auth()
        self.attach()

    def request(self, msg, tag=0):
        if tag == 0:
            tag = self.socket.addr_pool.alloc()
        try:
            msg['header']['tag'] = tag
            msg.reset()
            msg.encode()
            self.socket.msg_queue.ensure(tag)
            self.socket.send(msg.data)
            return tuple(self.socket.get(msg_seq=0))[0]
        finally:
            self.socket.addr_pool.free(tag, ban=0xFF)

    def version(self):
        m = msg_tversion()
        m['header']['tag'] = 0xFFFF
        m['msize'] = 8192
        m['version'] = '9P2000'
        return self.request(m, tag=0xFFFF)

    def auth(self):
        pass

    def attach(self):
        m = msg_tattach()
        m['fid'] = 0
        m['afid'] = 0xFFFFFFFF
        m['uname'] = pwd.getpwuid(os.getuid()).pw_name
        m['aname'] = ''
        return self.request(m)

    def walk(self, path, newfid=None, fid=None):
        m = msg_twalk()
        m['fid'] = self.cwd if fid is None else fid
        m['newfid'] = newfid if newfid is not None else self.fid_pool.alloc()
        m['wname'] = path.split(os.path.sep)
        self.wnames[path] = m['newfid']
        return self.request(m)

    def fid(self, path):
        if path not in self.wnames:
            newfid = self.fid_pool.alloc()
            self.walk(path, newfid)
            self.wnames[path] = newfid
        return self.wnames[path]

    def read(self, fid):
        m = msg_tread()
        m['fid'] = fid
        m['offset'] = 0
        m['count'] = 8192
        return self.request(m)

    def write(self, fid, data):
        m = msg_twrite()
        m['fid'] = fid
        m['offset'] = 0
        m['data'] = data
        return self.request(m)

    def call(self, fid, fname, argv=None, kwarg=None, data=b''):
        spec = {
            'call': fname,
            'argv': argv if argv is not None else [],
            'kwarg': kwarg if kwarg is not None else {},
        }
        m = msg_tcall()
        m['fid'] = fid
        m['text'] = json.dumps(spec)
        m['data'] = data
        return self.request(m)
