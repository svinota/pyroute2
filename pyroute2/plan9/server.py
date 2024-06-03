from pyroute2.plan9 import (
    Stat,
    Tattach,
    Tauth,
    Tclunk,
    Topen,
    Tread,
    Tstat,
    Tversion,
    Twalk,
    Twrite,
    msg_rattach,
    msg_rclunk,
    msg_rerror,
    msg_ropen,
    msg_rread,
    msg_rstat,
    msg_rversion,
    msg_rwalk,
    msg_rwrite,
)
from pyroute2.plan9.filesystem import Filesystem, Session
from pyroute2.plan9.plan9socket import Plan9Socket

data = str(dir())


def route(rtable, request, state):
    def decorator(f):
        def wrapped(*argv, **kwarg):
            try:
                return f(*argv, **kwarg)
            except Exception as e:
                m = msg_rerror()
                m['ename'] = repr(e)
                return m

        rtable[request] = wrapped
        return wrapped

    return decorator


class Plan9ClientConnection:
    rtable = {}

    def __init__(self, session, socket, address):
        self.socket = socket
        self.address = address
        self.session = session

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
        m['stat'] = self.session.get_fid(req['fid']).stat
        return m

    @route(rtable, request=Topen, state=(Twalk, Tstat))
    def t_open(self, req):
        m = msg_ropen()
        m['qid'] = self.session.get_fid(req['fid']).qid
        m['iounit'] = 8192
        return m

    @route(rtable, request=Twrite, state=(Topen,))
    def t_write(self, req):
        m = msg_rwrite()
        inode = self.session.get_fid(req['fid'])
        if inode.qid['type'] & 0x80:
            raise TypeError('can not call write() on dir')
        inode.data.seek(req['offset'])
        m['count'] = inode.data.write(req['data'])
        return m

    @route(rtable, request=Tread, state=(Topen,))
    def t_read(self, req):
        m = msg_rread()
        inode = self.session.get_fid(req['fid'])
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

    def serve(self):
        while True:
            request = self.socket.get()
            if len(request) != 1:
                return
            t_message = request[0]
            r_message = self.rtable[t_message['header']['type']](
                self, t_message
            )
            try:
                r_message.encode()
            except Exception as e:
                r_message = msg_rerror()
                r_message['ename'] = repr(e)
                r_message.encode()
            self.socket.send(r_message.data)


class Plan9Server:
    def __init__(self, address):
        self.socket = Plan9Socket()
        self.socket.bind(address)
        self.socket.listen(1)
        self.filesystem = Filesystem()

    def accept(self):
        session = Session(self.filesystem)
        return Plan9ClientConnection(session, *self.socket.accept())
