import asyncio
import json

from pyroute2.netlink.core import AsyncCoreSocket, CoreSocketSpec
from pyroute2.plan9 import (
    Marshal9P,
    Stat,
    Tattach,
    Tauth,
    Tcall,
    Tclunk,
    Tcreate,
    Topen,
    Tread,
    Tremove,
    Tstat,
    Tversion,
    Twalk,
    Twrite,
    Twstat,
    msg_rattach,
    msg_rcall,
    msg_rclunk,
    msg_rerror,
    msg_ropen,
    msg_rread,
    msg_rstat,
    msg_rversion,
    msg_rwalk,
    msg_rwrite,
    msg_rwstat,
)
from pyroute2.plan9.filesystem import Filesystem, Session

data = str(dir())


def get_exception_args(exc):
    args = []
    if hasattr(exc, 'errno'):
        args.append(exc.errno)
        args.append(exc.strerror)
    return args


def route(rtable, request, state):
    def decorator(f):
        rtable[request] = f
        return f

    return decorator


class Plan9ServerProtocol(asyncio.Protocol):
    rtable = {}

    def __init__(self, on_con_lost, marshal, filesystem):
        self.transport = None
        self.session = None
        self.filesystem = filesystem
        self.marshal = marshal
        self.on_con_lost = on_con_lost

    @route(rtable, request=Tversion, state=(None,))
    def t_version(self, req):
        m = msg_rversion()
        m['header']['tag'] = 0xFFFF
        m['msize'] = req['msize']
        m['version'] = '9P2000'
        return m

    @route(rtable, request=Tauth, state=(Tversion,))
    def t_auth(self, req):
        m = msg_rerror()
        m['ename'] = 'no authentication required'
        return m

    @route(rtable, request=Tattach, state=(Tauth,))
    def t_attach(self, req):
        m = msg_rattach()
        root = self.session.filesystem.inodes[0]
        self.session.set_fid(req['fid'], root)
        m['qid'] = root.qid
        return m

    @route(rtable, request=Twalk, state=(Tattach,))
    def t_walk(self, req):
        m = msg_rwalk()
        inode = self.session.get_fid(req['fid'])
        wqid = []
        if len(req['wname']) == 0:
            self.session.set_fid(req['newfid'], inode)
        else:
            for name in req['wname']:
                if name == '.':
                    continue
                elif name == '..':
                    inode = inode.get_parent()
                else:
                    inode = inode.get_child(name)
                wqid.append(inode.qid)
        m['wqid'] = wqid
        self.session.set_fid(req['newfid'], inode)
        return m

    @route(rtable, request=Tstat, state=(Twalk,))
    def t_stat(self, req):
        m = msg_rstat()
        inode = self.session.get_fid(req['fid'])
        inode.sync()
        m['stat'] = inode.stat
        return m

    @route(rtable, request=Twstat, state=(Twalk,))
    def t_wstat(self, req):
        m = msg_rwstat()
        return m

    @route(rtable, request=Topen, state=(Twalk, Tstat))
    def t_open(self, req):
        m = msg_ropen()
        m['qid'] = self.session.get_fid(req['fid']).qid
        m['iounit'] = 8192
        return m

    @route(rtable, request=Tcall, state=(Twalk, Topen, Tstat))
    def t_call(self, req):
        m = msg_rcall()
        inode = self.session.get_fid(req['fid'])
        m['err'] = 255
        if Tcall in inode.callbacks:
            m = inode.callbacks[Tcall](self.session, inode, req, m)
        return m

    @route(rtable, request=Twrite, state=(Topen,))
    def t_write(self, req):
        m = msg_rwrite()
        inode = self.session.get_fid(req['fid'])
        if Twrite in inode.callbacks:
            return inode.callbacks[Twrite](self.session, inode, req, m)
        if inode.qid['type'] & 0x80:
            raise TypeError('can not call write() on dir')
        inode.data.seek(req['offset'])
        m['count'] = inode.data.write(req['data'])
        return m

    @route(rtable, request=Tread, state=(Topen,))
    def t_read(self, req):
        m = msg_rread()
        inode = self.session.get_fid(req['fid'])
        if Tread in inode.callbacks:
            return inode.callbacks[Tread](self.session, inode, req, m)
        if inode.qid['type'] & 0x80:
            data = bytearray()
            offset = 0
            for child in inode.children:
                offset = Stat.encode_into(data, offset, child.stat)
            data = data[req['offset'] : req['offset'] + req['count']]
        else:
            inode.data.seek(req['offset'])
            data = inode.data.read(req['count'])
        m['data'] = data
        return m

    @route(rtable, request=Tclunk, state=(Topen, Tstat, Twalk, Tread))
    def t_clunk(self, req):
        return msg_rclunk()

    @route(rtable, request=Tcreate, state=(Twalk,))
    def t_create(self, req):
        return self.permission_denied(req)

    @route(rtable, request=Tremove, state=(Twalk,))
    def t_remove(self, req):
        return self.permission_denied(req)

    def permission_denied(self, req):
        r_message = msg_rerror()
        r_message['ename'] = 'permission denied'
        r_message['header']['tag'] = req['header']['tag']
        return r_message

    def error(self, e, tag=0):
        r_message = msg_rerror()
        spec = {
            'class': e.__class__.__name__,
            'argv': get_exception_args(e),
            'str': str(e),
        }
        r_message['ename'] = json.dumps(spec)
        r_message['header']['tag'] = tag
        r_message.encode()
        self.transport.write(r_message.data)

    def data_received(self, data):
        for t_message in self.marshal.parse(data):
            tag = t_message['header']['tag']
            try:
                r_message = self.rtable[t_message['header']['type']](
                    self, t_message
                )
                r_message['header']['tag'] = tag
                r_message.encode()
            except Exception as e:
                return self.error(e, tag)
            self.transport.write(r_message.data)

    def connection_made(self, transport):
        self.transport = transport
        self.session = Session(self.filesystem)


class Plan9ServerSocket(AsyncCoreSocket):
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
        self.filesystem = Filesystem()
        self.marshal = Marshal9P()
        super().__init__(use_socket=use_socket)

    async def setup_endpoint(self, loop=None):
        if self.endpoint is not None:
            return
        if self.status['use_socket']:
            self.endpoint = await self.event_loop.create_connection(
                lambda: Plan9ServerProtocol(
                    self.connection_lost, self.marshal, self.filesystem
                ),
                sock=self.use_socket,
            )
        else:
            self.endpoint = await self.event_loop.create_server(
                lambda: Plan9ServerProtocol(
                    self.connection_lost, self.marshal, self.filesystem
                ),
                *self.status['address']
            )

    async def async_run(self):
        await self.setup_endpoint()
        if self.status['use_socket']:
            return self.endpoint[1].on_con_lost
        else:
            return asyncio.create_task(self.endpoint.serve_forever())

    def run(self):
        self.event_loop.create_task(self.async_run())
        self.event_loop.run_forever()
