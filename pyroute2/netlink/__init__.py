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
        '''
        Set the buffer and return the data length
        '''
        self.buf = io.BytesIO()
        self.buf.write(init)
        self.buf.seek(0)
        return len(init)

    def parse(self, data):
        '''
        Parse the data in the buffer
        '''
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

    def reload(self):
        '''
        Placeholder for methods to reload poll/select cycle.
        It should be re-defined in derived classes.
        '''
        pass

    def register(self, fd):
        '''
        Register a new fd/socket for poll/select cycle.
        '''
        self._rlist.append(fd)
        self.reload()

    def unregister(self, fd):
        '''
        Remove a fd/socket from polling.
        '''
        self._rlist.pop(self._rlist.index(fd))
        self.reload()

    def parse(self, data):
        '''
        Parse and enqueue messages. A message can be
        retrieved from netlink socket as well as from a
        remote system, and it should be properly enqueued
        to make it available for netlink.get() method.

        If iothread.mirror is set, all messages will be also
        copied (mirrored) to the default 0 queue. Please
        make sure that 0 queue exists, before setting
        iothread.mirror to True.

        If there is no such queue for received
        sequence_number, leave sequence_number intact, but
        put the message into default 0 queue, if it exists.
        '''

        # TODO: create a hook for custom cmdmsg?

        for msg in self.marshal.parse(data):
            key = msg['header']['sequence_number']
            if key not in self.listeners:
                key = 0
            if self.mirror and key != 0:
                self.listeners[0].put(copy.deepcopy(msg))
            if key in self.listeners:
                self.listeners[key].put(msg)


class zmq_io(iothread):
    '''
    Thread to monitor ZMQ I/O. ZMQ sockets polling actually
    can be integrated with common poll/select, but it is
    easier to use zmq.select and keep it in a separate thread.

    zmq_io has also its own controlling ZMQ socket,
    zmq_io.control, that can be used to communicate with
    the thread. Right now messages are not interpreted
    and all they do -- they cause zmq.select to make one more
    turn, reloading zmq_io._rlist.

    If you want to extend this functionality, look at
    zmq_io.reload() and comments in zmq_io.run()
    '''

    def __init__(self, marshal, ctx, send_method=None):
        iothread.__init__(self, marshal)
        self.send = send_method
        self._ctlr = ctx.socket(zmq.PAIR)
        self._ctlr.bind('inproc://bala')
        self.control = ctx.socket(zmq.PAIR)
        self.control.connect('inproc://bala')
        self.register(self._ctlr)

    def reload(self):
        '''
        Send a message to reload self._rlist. This method is
        called automatically each time when you call
        zmq_io.register()/zmq_io.unregister().
        '''
        self.control.send("reload")

    def run(self):
        while True:
            [rlist, wlist, xlist] = zmq.select(self._rlist, [], [])
            for fd in rlist:
                data = fd.recv()
                if fd != self._ctlr:
                    # TODO: to make it possible to parse
                    # control messages both on client and
                    # server side, this choice should be moved
                    # inside iothread.parse()
                    if self.send is not None:
                        # If we have a method to send messages,
                        # bypass them there.
                        #
                        # This branch works in the server, sending
                        # client messages to the kernel.
                        self.send(data)
                    else:
                        # Otherwise, parse the message.
                        #
                        # This branch works in the client, receiving
                        # and parsing messages from server
                        self.parse(data)
                else:
                    # TODO: here you can place hooks to
                    # interpret messages, sent via zmq_io.control
                    # socket.
                    pass


class netlink_io(iothread):
    '''
    Netlink I/O thread. It receives messages from the
    kernel via netlink socket[s] and enqueues them and
    send via ZMQ to subscribers, if there are any.
    '''
    def __init__(self, marshal, family, groups):
        iothread.__init__(self, marshal)
        self.socket = netlink_socket(family)
        self.socket.bind(groups)
        (self._ctlr, self.control) = os.pipe()
        self._rlist.append(self._ctlr)
        self._rlist.append(self.socket)
        self._stop = False

    def register_relay(self, sock):
        '''
        Register ZMQ PUB socket to publish messages on.
        There is no need to reload poll/select cycle after
        that.
        '''
        self._wlist.append(sock)

    def unregister_relay(self, sock):
        '''
        Remove ZMQ PUB socket.
        '''
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
    '''
    Main netlink messaging class. It automatically spawns threads
    to monitor ZMQ and netlink I/O, creates and destroys message
    queues.

    It can operate in three modes:
     * local system only
     * server mode
     * client mode

    By default, it starts in local system only mode. To start a
    server, you should call netlink.add_server(url). The method
    can be called several times to listen on specific interfaces
    and/or ports.

    Alternatively, you can start the object in the client mode.
    In that case you should provide server url in the host
    parameter. You can not mix server and client modes, so
    message proxy/relay not possible yet. This will be fixed
    in the future.

    Urls should be specified in the form:
        scheme://host:PUSH/PULL_port:PUB/SUB_port

    E.g.:
        nl = netlink(host='tcp://127.0.0.1:7001:7002')

    Why two ports? Netlink is asynchronous datagram protocol
    like UDP, where both sides can send and receive messages.
    There is no sessions, the message relevance is reflected
    in sequence_number field, that acts like a cookie. To
    make it possible to work transparently over networks with
    SNAT/DNAT, it is simpler to use two TCP connections, one
    to send messages with PUSH and one to wait for PUB/SUB
    broadcasts.
    '''

    family = NETLINK_GENERIC
    groups = 0
    marshal = marshal

    def __init__(self, debug=False, host='localsystem', ctx=None):
        self.host = host
        if host == 'localsystem':
            self.ctx = ctx
            self.zmq_thread = None
            self.io_thread = netlink_io(self.marshal, self.family,
                                        self.groups)
            self.io_thread.start()
            self.socket = self.io_thread.socket
            self.listeners = self.io_thread.listeners
        else:
            self.ctx = ctx or zmq.Context()
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
        '''
        Remove server socket, a specified one or just
        the first.
        '''
        url = url or self.servers.keys()[0]
        self.zmq_thread.unregister(self.servers[url]['rep'])
        self.zmq_thread.reload()
        self.io_thread.unregister_relay(self.servers[url]['pub'])
        self.servers.pop(url)

    def add_server(self, url):
        '''
        Add server ZMQ socket to listen on. The method
        creates both PULL and PUB sockets and registers
        them for I/O monitoring.
        '''
        if self.ctx is None:
            self.ctx = zmq.Context()
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
        Increment netlink protocol nonce (there is no need to
        call it directly)
        '''
        if self._nonce == 0xffffffff:
            self._nonce = 1
        else:
            self._nonce += 1
        return self._nonce

    def mirror(self, operate=True):
        '''
        Turn message mirroring on/off. When it is 'on', all
        received messages will be copied (mirrored) into the
        default 0 queue.
        '''
        self.monitor(operate)
        if self.io_thread is not None:
            self.io_thread.mirror = operate
        if self.zmq_thread is not None:
            self.zmq_thread.mirror = operate

    def monitor(self, operate=True):
        '''
        Create/destroy the default 0 queue. Netlink socket
        receives messages all the time, and there are many
        messages that are not replies. They are just
        generated by the kernel as a reflection of settings
        changes. To start receiving these messages, call
        netlink.monitor(). They can be fetched by
        netlink.get(0) or just netlink.get().
        '''
        if operate:
            self.listeners[0] = Queue.Queue()
        else:
            del self.listeners[0]

    def stop(self):
        # FIXME
        msg = cmdmsg(io.BytesIO())
        msg['command'] = IPRCMD_STOP
        msg.encode()
        os.write(self.io_thread.control, msg.buf.getvalue())

    def get(self, key=0, interruptible=False):
        '''
        Get a message from a queue

        * key -- message queue number
        * interruptible -- catch ctrl-c

        Please note, that setting interruptible=True will cause
        polling overhead. Python starts implied poll cycle, if
        timeout is set.
        '''
        queue = self.listeners[key]
        if interruptible:
            tot = 31536000
        else:
            tot = None
        result = []
        while True:
            # timeout is set to catch ctrl-c
            # Bug-Url: http://bugs.python.org/issue1360
            msg = queue.get(block=True, timeout=tot)
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
                msg = queue.get(bloc=True, timeout=tot)
                if 0 in self.listeners:
                    self.listeners[0].put(msg)
        return result

    def send(self, buf):
        '''
        Send a buffer or to the local kernel, or to
        the server, depending on the setup.
        '''
        if self.host == 'localsystem':
            self.socket.sendto(buf, (0, 0))
        else:
            self.socket.send(buf)

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST):
        '''
        Send netlink request, filling common message
        fields, and wait for response.
        '''
        # FIXME make it thread safe, yeah
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
