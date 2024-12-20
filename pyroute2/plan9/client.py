import json
import os
import pwd
import struct

from pyroute2.common import AddrPool
from pyroute2.netlink.core import (
    AsyncCoreSocket,
    CoreSocketSpec,
    CoreStreamProtocol,
)
from pyroute2.plan9 import (
    Marshal9P,
    msg_tattach,
    msg_tcall,
    msg_tread,
    msg_tversion,
    msg_twalk,
    msg_twrite,
)


class Plan9ClientSocket(AsyncCoreSocket):
    def __init__(self, address=None, use_socket=None):
        self.spec = CoreSocketSpec(
            {
                'tag_field': 'tag',
                'target': 'localhost',
                'netns': None,
                'address': address,
                'use_socket': use_socket is not None,
            }
        )
        self.marshal = Marshal9P()
        self.wnames = {'': 0}
        self.cwd = 0
        self.fid_pool = AddrPool(minaddr=0x00000001, maxaddr=0x0000FFFF)
        super().__init__(use_socket=use_socket)

    def enqueue(self, data, addr):
        tag = struct.unpack_from('H', data, 5)[0]
        return self.msg_queue.put_nowait(tag, data)

    async def setup_socket(self, sock=None):
        return sock

    async def setup_endpoint(self, loop=None):
        if self.endpoint is not None:
            return
        if self.status['use_socket']:
            address = {'sock': self.use_socket}
        else:
            address = {
                'host': self.status['address'][0],
                'port': self.status['address'][1],
            }
        self.endpoint = await self.event_loop.create_connection(
            lambda: CoreStreamProtocol(self.connection_lost, self.enqueue),
            **address,
        )

    async def start_session(self):
        await self.ensure_socket()
        await self.version()
        await self.auth()
        await self.attach()

    async def request(self, msg, tag=0):
        await self.ensure_socket()
        if tag == 0:
            tag = self.addr_pool.alloc()
        try:
            msg['header']['tag'] = tag
            msg.reset()
            msg.encode()
            self.msg_queue.ensure_tag(tag)
            self.endpoint[0].write(msg.data)
            return [x async for x in self.get(msg_seq=tag)][0]
        finally:
            self.addr_pool.free(tag, ban=0xFF)

    async def version(self):
        m = msg_tversion()
        m['header']['tag'] = 0xFFFF
        m['msize'] = 8192
        m['version'] = '9P2000'
        return await self.request(m, tag=0xFFFF)

    async def auth(self):
        pass

    async def attach(self):
        m = msg_tattach()
        m['fid'] = 0
        m['afid'] = 0xFFFFFFFF
        m['uname'] = pwd.getpwuid(os.getuid()).pw_name
        m['aname'] = ''
        return await self.request(m)

    async def walk(self, path, newfid=None, fid=None):
        m = msg_twalk()
        m['fid'] = self.cwd if fid is None else fid
        m['newfid'] = newfid if newfid is not None else self.fid_pool.alloc()
        m['wname'] = path.split(os.path.sep)
        self.wnames[path] = m['newfid']
        return await self.request(m)

    async def fid(self, path):
        if path not in self.wnames:
            newfid = self.fid_pool.alloc()
            await self.walk(path, newfid)
            self.wnames[path] = newfid
        return self.wnames[path]

    async def read(self, fid):
        m = msg_tread()
        m['fid'] = fid
        m['offset'] = 0
        m['count'] = 8192
        return await self.request(m)

    async def write(self, fid, data):
        m = msg_twrite()
        m['fid'] = fid
        m['offset'] = 0
        m['data'] = data
        return await self.request(m)

    async def call(
        self, fid, fname='', argv=None, kwarg=None, data=b'', data_arg='data'
    ):
        spec = {
            'call': fname,
            'argv': argv if argv is not None else [],
            'kwarg': kwarg if kwarg is not None else {},
            'data_arg': data_arg,
        }
        m = msg_tcall()
        m['fid'] = fid
        m['text'] = json.dumps(spec)
        m['data'] = data
        return await self.request(m)
