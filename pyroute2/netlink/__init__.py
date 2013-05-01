import threading
import select
import struct
import socket
import Queue
import copy
import os
import io
import zmq

from pyroute2.netlink.generic import cmdmsg
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import NETLINK_GENERIC


## Netlink message flags values (nlmsghdr.flags)
#
NLM_F_REQUEST = 1    # It is request message.
NLM_F_MULTI = 2    # Multipart message, terminated by NLMSG_DONE
NLM_F_ACK = 4    # Reply with ack, with zero or error code
NLM_F_ECHO = 8    # Echo this request
# Modifiers to GET request
NLM_F_ROOT = 0x100    # specify tree    root
NLM_F_MATCH = 0x200    # return all matching
NLM_F_ATOMIC = 0x400    # atomic GET
NLM_F_DUMP = (NLM_F_ROOT | NLM_F_MATCH)
# Modifiers to NEW request
NLM_F_REPLACE = 0x100    # Override existing
NLM_F_EXCL = 0x200    # Do not touch, if it exists
NLM_F_CREATE = 0x400    # Create, if it does not exist
NLM_F_APPEND = 0x800    # Add to end of list

NLMSG_NOOP = 0x1    # Nothing
NLMSG_ERROR = 0x2    # Error
NLMSG_DONE = 0x3    # End of a dump
NLMSG_OVERRUN = 0x4    # Data lost
NLMSG_MIN_TYPE = 0x10    # < 0x10: reserved control messages
NLMSG_MAX_LEN = 0xffff  # Max message length

IPRCMD_NOOP = 1
IPRCMD_REGISTER = 2
IPRCMD_UNREGISTER = 3
IPRCMD_STOP = 4
IPRCMD_RELOAD = 5


class netlink_error(socket.error):
    def __init__(self, code, msg=None):
        msg = msg or os.strerror(code)
        super(netlink_error, self).__init__(code, msg)
        self.code = code


class marshal(object):
    '''
    Generic marshalling class
    '''

    msg_map = {}

    def __init__(self):
        self.lock = threading.Lock()
        # one marshal instance can be used to parse one
        # message at once
        self.buf = None
        self.msg_map = self.msg_map or {}

    def set_buffer(self, init=b''):
        self.buf = io.BytesIO()
        self.buf.write(init)
        self.buf.seek(0)
        return len(init)

    def parse(self, data):
        with self.lock:
            total = self.set_buffer(data)
            offset = 0
            result = []

            while offset < total:
                # pick type and length
                (length, msg_type) = struct.unpack('IH', self.buf.read(6))
                error = None
                if msg_type == NLMSG_ERROR:
                    self.buf.seek(16)
                    code = abs(struct.unpack('i', self.buf.read(4))[0])
                    if code > 0:
                        error = netlink_error(code)

                self.buf.seek(offset)
                msg_class = self.msg_map.get(msg_type, nlmsg)
                msg = msg_class(self.buf)
                msg.decode()
                msg['header']['error'] = error
                self.fix_message(msg)
                offset += msg.length
                result.append(msg)

            return result

    def fix_message(self, msg):
        pass


class netlink_socket(socket.socket):
    '''
    Generic netlink socket
    '''

    def __init__(self, family=NETLINK_GENERIC):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        self.pid = os.getpid()
        self.groups = None

    def bind(self, groups=0):
        self.groups = groups
        socket.socket.bind(self, (self.pid, self.groups))

class iothread(threading.Thread):
    def __init__(self, marshal):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self._rlist = []
        self._wlist = []
        self._xlist = []
        self.marshal = marshal()
        self.listeners = {}
        self.mirror = False

    def register(self, fd):
        self._rlist.append(fd)

    def unregister(self, fd):
        self._rlist.pop(self._rlist.index(fd))

    def parse(self, data):
        for msg in self.marshal.parse(data):
            key = msg['header']['sequence_number']
            if key not in self.listeners:
                key = 0
            if self.mirror and key != 0:
                self.listeners[0].put(copy.deepcopy(msg))
            if key in self.listeners:
                self.listeners[key].put(msg)


class zmq_io(iothread):

    def __init__(self, marshal, ctx, send_method=None):
        iothread.__init__(self, marshal)
        self.send = send_method
        self._ctlr = ctx.socket(zmq.PAIR)
        self._ctlr.bind('inproc://bala')
        self.control = ctx.socket(zmq.PAIR)
        self.control.connect('inproc://bala')
        self.register(self._ctlr)

    def reload(self):
        self.control.send("reload")

    def run(self):
        while True:
            [rlist, wlist, xlist] = zmq.select(self._rlist, [], [])
            for fd in rlist:
                data = fd.recv()
                if fd != self._ctlr:
                    if self.send is not None:
                        self.send(data)
                    else:
                        self.parse(data)


class netlink_io(iothread):
    def __init__(self, marshal, family, groups):
        iothread.__init__(self, marshal)
        self.socket = netlink_socket(family)
        self.socket.bind(groups)
        (self._ctlr, self.control) = os.pipe()
        self._rlist.append(self._ctlr)
        self._rlist.append(self.socket)
        self._stop = False

    def register_relay(self, sock):
        self._wlist.append(sock)

    def unregister_relay(self, sock):
        self._wlist.pop(self._wlist.index(sock))

    def run(self):
        while not self._stop:
            [rlist, wlist, xlist] = select.select(self._rlist, [], [])
            for fd in rlist:
                if fd == self._ctlr:
                    buf = io.BytesIO()
                    buf.write(os.read(self._ctlr, 6))
                    buf.seek(0)
                    cmd = cmdmsg(buf)
                    if cmd['command'] == IPRCMD_STOP:
                        self._stop = True
                        break
                    elif cmd['command'] == IPRCMD_RELOAD:
                        pass

                elif fd == self.socket:
                    data = fd.recv(16384)
                    for sock in self._wlist:
                        sock.send(data)
                    self.parse(data)


class netlink(object):

    family = NETLINK_GENERIC
    groups = 0
    marshal = marshal

    def __init__(self, debug=False, host='localsystem', ctx=None):
        self.ctx = ctx
        self.host = host
        if host == 'localsystem':
            self.zmq_thread = None
            self.io_thread = netlink_io(self.marshal, self.family,
                                        self.groups)
            self.io_thread.start()
            self.socket = self.io_thread.socket
            self.listeners = self.io_thread.listeners
        else:
            self.io_thread = None
            (scheme, host, port_req, port_sub) = host.split(':')
            self.socket = ctx.socket(zmq.PUSH)
            self.socket.connect('%s:%s:%s' % (scheme, host, port_req))
            sub = ctx.socket(zmq.SUB)
            sub.connect('%s:%s:%s' % (scheme, host, port_sub))
            sub.setsockopt(zmq.SUBSCRIBE, '')
            self.zmq_thread = zmq_io(self.marshal, self.ctx)
            self.zmq_thread.start()
            self.zmq_thread.register(sub)
            self.zmq_thread.reload()
            self.listeners = self.zmq_thread.listeners
        self.debug = debug
        self._nonce = 1
        self.servers = {}

    def pop_server(self, url=None):
        url = url or self.servers.keys()[0]
        self.zmq_thread.unregister(self.servers[url]['rep'])
        self.zmq_thread.reload()
        self.io_thread.unregister_relay(self.servers[url]['pub'])
        self.servers.pop(url)

    def add_server(self, url):
        if self.zmq_thread is None:
            self.zmq_thread = zmq_io(self.marshal, self.ctx, self.send)
            self.zmq_thread.start()
        (scheme, host, port_rep, port_pub) = url.split(':')
        rep = self.ctx.socket(zmq.PULL)
        rep.bind('%s:%s:%s' % (scheme, host, port_rep))
        pub = self.ctx.socket(zmq.PUB)
        pub.bind('%s:%s:%s' % (scheme, host, port_pub))
        self.servers[url] = {'rep': rep,
                             'pub': pub}
        self.zmq_thread.register(rep)
        self.zmq_thread.reload()
        self.io_thread.register_relay(pub)

    def nonce(self):
        '''
        Increment netlink protocol nonce (there is no need to call it directly)
        '''
        if self._nonce == 0xffffffff:
            self._nonce = 1
        else:
            self._nonce += 1
        return self._nonce

    def mirror(self, operate=True):
        if self.io_thread is not None:
            self.io_thread.mirror = operate
        if self.zmq_thread is not None:
            self.zmq_thread.mirror = operate

    def monitor(self, operate=True):
        if operate:
            self.listeners[0] = Queue.Queue()
        else:
            del self.listeners[0]

    def stop(self):
        msg = cmdmsg(io.BytesIO())
        msg['command'] = IPRCMD_STOP
        msg.encode()
        os.write(self.io_thread.control, msg.buf.getvalue())

    def get(self, key=0, blocking=True):
        '''
        Get a message from a queue
        '''
        queue = self.listeners[key]

        result = []
        while True:
            msg = queue.get()
            if msg['header']['error'] is not None:
                raise msg['header']['error']
            if msg['header']['type'] != NLMSG_DONE:
                result.append(msg)
            if (msg['header']['type'] == NLMSG_DONE) or \
               (not msg['header']['flags'] & NLM_F_MULTI):
                break
        # not default queue
        if key != 0:
            # delete the queue
            del self.listeners[key]
            # get remaining messages from the queue and
            # re-route them to queue 0 or drop
            while not queue.empty():
                msg = queue.get()
                if 0 in self.listeners:
                    self.listeners[0].put(msg)
        return result

    def send(self, buf):
        if self.host == 'localsystem':
            self.socket.sendto(buf, (0, 0))
        else:
            self.socket.send(buf)

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST):
        nonce = self.nonce()
        self.listeners[nonce] = Queue.Queue()
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg.encode()
        self.send(msg.buf.getvalue())
        result = self.get(nonce)
        if not self.debug:
            for i in result:
                del i['header']
        return result
