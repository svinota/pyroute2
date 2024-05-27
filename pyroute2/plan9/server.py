from pyroute2.plan9.plan9socket import Plan9Socket
from pyroute2.plan9 import (
        Tversion,
        Rversion,
        Tauth,
        Rauth,
        Tattach,
        Rattach,
        Terror,
        Rerror,
        Twalk,
        Rwalk,
        Tstat,
        Rstat,
        Topen,
        Ropen,
        Tread,
        Rread,
        Tclunk,
        Rclunk,
        msg_rversion,
        msg_rauth,
        msg_rattach,
        msg_rerror,
        msg_rwalk,
        msg_rstat,
        msg_ropen,
        msg_rread,
        msg_rclunk,
    )

data = str(dir())

def route(rtable, request, state, response):
    def decorator(f):
        rtable[request] = f
        return f
    return decorator


class Plan9ClientConnection:
    rtable = {}

    def __init__(self, socket, address):
        self.socket = socket
        self.address = address

    @route(rtable, request=Tversion, state=(None, ), response=(Rversion, Rerror))
    def t_version(self, req):
        m = msg_rversion()
        m['header']['tag'] = 0xffff
        m['msize'] = req['msize']
        m['version'] = '9P2000'
        return m

    @route(rtable, request=Tauth, state=(Tversion, ), response=(Rauth, Rerror))
    def t_auth(self, req):
        m = msg_rerror()
        m['ename'] = 'no authentication required'
        return m

    @route(rtable, request=Tattach, state=(Tauth, ), response=(Rattach, Rerror))
    def t_attach(self, req):
        m = msg_rattach()
        m['qid'] = {'type': 0x80, 'vers': 0, 'path': 0}
        return m

    @route(rtable, request=Twalk, state=(Tattach, ), response=(Rwalk, Rerror))
    def t_walk(self, req):
        m = msg_rwalk()
        if len(req['wname']) == 0:
            wqid = []
        elif len(req['wname']) == 1 and req['wname'][0] == 'test':
            wqid = [{'type': 0, 'vers': 0, 'path': 265}]
        else:
            e = msg_rerror()
            e['ename'] = 'file not found'
            return e
        m['wqid'] = wqid
        return m

    @route(rtable, request=Tstat, state=(Twalk, ), response=(Rstat, Rerror))
    def t_stat(self, req):
        if req['fid'] != 1:
            m = msg_rerror()
            m['ename'] = 'file not found'
            return m
        global data
        m = msg_rstat()
        m['type'] = 265
        m['dev'] = 0
        m['qid.type'] = 0
        m['qid.vers'] = 0
        m['qid.path'] = 265
        m['mode'] = 0o010_000_000_600
        m['atime'] = m['mtime'] = time.time()
        m['length'] = len(data)
        m['name'] = 'test'
        m['uid'] = 'peet'
        m['gid'] = 'peet'
        m['muid'] = 'peet'
        m['plength'] = 65
        m['size'] = 63
        return m

    @route(rtable, request=Topen, state=(Twalk, Tstat), response=(Ropen, Rerror))
    def t_open(self, req):
        m = msg_ropen()
        m['qid'] = {'type': 0, 'vers': 0, 'path': 265}
        m['iounit'] = 8192
        return m

    @route(rtable, request=Tread, state=(Topen, ), response=(Rread, Rerror))
    def t_read(self, req):
        global data
        m = msg_rread()
        m['data'] = data[req['offset']:req['offset'] + 8192]
        return m

    @route(rtable, request=Tclunk, state=(Topen, Tstat, Twalk, Tread), response=(Rclunk, Rerror))
    def t_clunk(self, req):
        return msg_rclunk()

    def serve(self):
        while True:
            request = self.socket.get()
            if len(request) != 1:
                return
            t_message = request[0]
            r_message = self.rtable[t_message['header']['type']](self, t_message)
            r_message.encode()
            self.socket.send(r_message.data)


class Plan9Server:
    def __init__(self, address):
        self.socket = Plan9Socket()
        self.socket.bind(address)
        self.socket.listen(1)

    def accept(self):
        return Plan9ClientConnection(*self.socket.accept())
