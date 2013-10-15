import traceback
import threading
import urlparse
import logging
import select
import struct
import socket
import Queue
import time
import os
import io
import uuid
import ssl

from pyroute2.netlink.generic import ctrlmsg
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import NetlinkDecodeError
from pyroute2.netlink.generic import NetlinkHeaderDecodeError
from pyroute2.netlink.generic import NETLINK_GENERIC
from pyroute2.netlink.generic import NETLINK_UNUSED


_QUEUE_MAXSIZE = 4096


class NetlinkError(Exception):
    '''
    Base netlink error
    '''
    def __init__(self, code, msg=None):
        msg = msg or os.strerror(code)
        super(NetlinkError, self).__init__(code, msg)
        self.code = code


##
# FIXME: achtung, monkeypatch!
#
# Android QPython 2.7 platform has no AF_UNIX, so add some
# invalid value just not to fail on checks.
#
if not hasattr(socket, 'AF_UNIX'):
    socket.AF_UNIX = 65535


def _monkey_handshake(self):
    ##
    # FIXME: achtung, monkeypatch!
    #
    # We have to close incoming connection on handshake error.
    # But if the handshake method is called from the SSLSocket
    # constructor, there is no way to close it: we loose all
    # the references to the failed connection, except the
    # traceback.
    #
    # Using traceback (via sys.exc_info()) can lead to
    # unpredictable consequences with GC. So we have two more
    # choices:
    # 1. use monkey-patch for do_handshake()
    # 2. call it separately.
    #
    # The latter complicates the code by extra checks, that
    # will not be needed most of the time. So the monkey-patch
    # is cheaper.
    #
    ##
    try:
        self._sslobj.do_handshake()
    except Exception as e:
        self._sock.close()
        raise e


ssl.SSLSocket.do_handshake = _monkey_handshake


AF_PIPE = 255  # Right now AF_MAX == 40

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

mtypes = {1: 'NLMSG_NOOP',
          2: 'NLMSG_ERROR',
          3: 'NLMSG_DONE',
          4: 'NLMSG_OVERRUN'}

IPRCMD_NOOP = 0
IPRCMD_STOP = 1
IPRCMD_ACK = 2
IPRCMD_ERR = 3
IPRCMD_REGISTER = 4
IPRCMD_RELOAD = 5
IPRCMD_ROUTE = 6


def _get_plugin(url):
    scheme, command = url.split('://')
    name = 'plugin_%s' % (scheme)
    plugins = __import__('pyroute2.netlink.plugins',
                         globals(),
                         locals(),
                         [name],
                         -1)
    plugin = getattr(plugins, name)
    return (plugin.plugin_init['type'],
            plugin.plugin_init['create'],
            command)


def _get_socket(url, server_side=False, ssl_keys=None):
    assert url[:6] in ('tcp://', 'ssl://', 'tls://') or \
        url[:11] in ('unix+ssl://', 'unix+tls://') or url[:7] == 'unix://'
    target = urlparse.urlparse(url)
    hostname = target.hostname or ''
    ssl_keys = ssl_keys or {}
    use_ssl = False
    ssl_version = 2

    if target.scheme[:4] == 'unix':
        if hostname and hostname[0] == '\0':
            address = hostname
        else:
            address = ''.join((hostname, target.path))
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    else:
        address = (socket.gethostbyname(hostname), target.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if target.scheme.find('ssl') >= 0:
        ssl_version = ssl.PROTOCOL_SSLv3
        use_ssl = True

    if target.scheme.find('tls') >= 0:
        ssl_version = ssl.PROTOCOL_TLSv1
        use_ssl = True

    if use_ssl:
        if url not in ssl_keys:
            raise Exception('SSL/TLS keys are not provided')

        sock = ssl.wrap_socket(sock,
                               keyfile=ssl_keys[url].key,
                               certfile=ssl_keys[url].cert,
                               ca_certs=ssl_keys[url].ca,
                               server_side=server_side,
                               cert_reqs=ssl.CERT_REQUIRED,
                               ssl_version=ssl_version)
    return (sock, address)


def _repr_sockets(sockets, mode):
    '''
    Represent socket as a text string
    '''
    ret = []
    for i in sockets:
        url = ''
        if isinstance(i, NetlinkSocket):
            ret.append('netlink://%s' % (i.family))
            continue

        if i.family == socket.AF_UNIX:
            url = 'unix'
        elif i.family == AF_PIPE:
            url = 'pipe'
        if type(i) == ssl.SSLSocket:
            if url:
                url += '+'
            if i.ssl_version == ssl.PROTOCOL_SSLv3:
                url += 'ssl'
            elif i.ssl_version == ssl.PROTOCOL_TLSv1:
                url += 'tls'
        if not url:
            url = 'tcp'
        if i.family == socket.AF_UNIX:
            url += '://%s' % (i.getsockname())
        elif i.family == AF_PIPE:
            url += '://%i,%i' % (i.getsockname())
        else:
            if mode == 'local':
                url += '://%s:%i' % (i.getsockname())
            elif mode == 'remote':
                url += '://%s:%i' % (i.getpeername())
        ret.append(url)
    return ret


class Marshal(object):
    '''
    Generic marshalling class
    '''

    msg_map = {}
    debug = False

    def __init__(self):
        self.lock = threading.Lock()
        # one marshal instance can be used to parse one
        # message at once
        self.msg_map = self.msg_map or {}

    def parse(self, data):
        '''
        Parse the data in the buffer
        '''
        with self.lock:
            total = data.length
            data.seek(0)
            offset = 0
            result = []

            while offset < total:
                # pick type and length
                (length, msg_type) = struct.unpack('IH', data.read(6))
                error = None
                if msg_type == NLMSG_ERROR:
                    data.seek(offset + 16)
                    code = abs(struct.unpack('i', data.read(4))[0])
                    if code > 0:
                        error = NetlinkError(code)

                data.seek(offset)
                msg_class = self.msg_map.get(msg_type, nlmsg)
                msg = msg_class(data, debug=self.debug)
                try:
                    msg.decode()
                    msg['header']['error'] = error
                except NetlinkHeaderDecodeError as e:
                    # in the case of header decoding error,
                    # create an empty message
                    msg = nlmsg()
                    msg['header']['error'] = e
                except NetlinkDecodeError as e:
                    msg['header']['error'] = e
                mtype = msg['header'].get('type', None)
                if mtype in (1, 2, 3, 4):
                    msg['event'] = mtypes.get(mtype, 'none')
                self.fix_message(msg)
                offset += msg.length
                result.append(msg)

            return result

    def fix_message(self, msg):
        pass


class PipeSocket(object):
    '''
    Socket-like object for one-system IPC.

    It is netlink-specific, since relies on length value
    provided in the first four bytes of each message.
    '''

    family = AF_PIPE

    def __init__(self, rfd, wfd):
        self.rfd = rfd
        self.wfd = wfd

    def send(self, data):
        os.write(self.wfd, data)

    def recv(self, length=0, flags=0):
        ret = os.read(self.rfd, 4)
        length = struct.unpack('I', ret)[0]
        ret += os.read(self.rfd, length - 4)
        return ret

    def getsockname(self):
        return self.rfd, self.wfd

    def fileno(self):
        return self.rfd

    def close(self):
        os.close(self.rfd)
        os.close(self.wfd)


def pairPipeSockets():
    pipe0_r, pipe0_w = os.pipe()
    pipe1_r, pipe1_w = os.pipe()
    return PipeSocket(pipe0_r, pipe1_w), PipeSocket(pipe1_r, pipe0_w)


class NetlinkSocket(socket.socket):
    '''
    Generic netlink socket
    '''

    def __init__(self, family=NETLINK_GENERIC):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        self.pid = os.getpid()
        self.groups = 0
        self.marshal = None

    def bind(self, groups=0):
        self.groups = groups
        socket.socket.bind(self, (self.pid, self.groups))

    def get(self):
        data = io.BytesIO()
        data.length = data.write(self.recv(16384))
        return self.marshal.parse(data)


class ssl_credentials(object):
    def __init__(self, key, cert, ca):
        self.key = key
        self.cert = cert
        self.ca = ca


class masq_record(object):
    def __init__(self, seq, pid, socket):
        self.seq = seq
        self.pid = pid
        self.socket = socket
        self.ctime = time.time()

    def __repr__(self):
        return "%s, %s, %s, %s" % (_repr_sockets([self.socket], 'remote'),
                                   self.pid, self.seq, time.ctime(self.ctime))


class IOThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self, name='Netlink I/O')
        self.setDaemon(True)
        self.pid = os.getpid()
        self._nonce = 0
        self._nonce_lock = threading.Lock()
        self._run_event = threading.Event()
        self._sctl_event = threading.Event()
        self._stop_event = threading.Event()
        self._reload_event = threading.Event()
        # fd lists for select()
        self._rlist = set()
        self._wlist = set()
        self._xlist = set()
        # routing
        self.rtable = {}          # {client_socket: send_method, ...}
        self.families = {}        # {family_id: send_method, ...}
        self.marshals = {}        # {netlink_socket: marshal, ...}
        self.listeners = {}       # {int: Queue(), int: Queue()...}
        self.masquerade = {}      # {int: masq_record()...}
        self.recv_methods = {}    # {socket: recv_method, ...}
        self.clients = set()      # set(socket, socket...)
        self.uplinks = set()      # set(socket, socket...)
        self.servers = set()      # set(socket, socket...)
        self.controls = set()     # set(socket, socket...)
        self.broadcast = set()    # set(socket, socket...)
        self.ssl_keys = {}        # {url: ssl_credentials(), url:...}
        self.mirror = False
        self.callbacks = []       # [(predicate, callback, args), ...]
        # secret; write non-zero byte as terminator
        self.secret = os.urandom(15)
        self.secret += '\xff'
        self.uuid = uuid.uuid4()
        # control in-process communication only
        self.sctl, self.control = pairPipeSockets()
        self.add_client(self.sctl)
        self._sctl_thread = threading.Thread(target=self._sctl,
                                             name='IPC init')
        self._sctl_thread.start()
        # masquerade cache expiration
        self._expire_thread = threading.Thread(target=self._expire_masq,
                                               name='Masquerade cache')
        self._expire_thread.setDaemon(True)
        self._expire_thread.start()
        # buffers reassembling
        self.buffers = Queue.Queue()
        self._feed_thread = threading.Thread(target=self._feed_buffers,
                                             name='Reasm and parsing')
        self._feed_thread.setDaemon(True)
        self._feed_thread.start()
        # debug
        self.record = False
        self.backlog = []

    def _sctl(self):
        msg = ctrlmsg()
        msg['header']['type'] = NETLINK_UNUSED
        msg['cmd'] = IPRCMD_REGISTER
        msg['attrs'] = [['IPR_ATTR_SECRET', self.secret]]
        msg.encode()
        self._run_event.wait()
        self.control.send(msg.buf.getvalue())
        buf = io.BytesIO()
        buf.write(self.control.recv(256))
        buf.seek(0)
        msg = ctrlmsg(buf)
        msg.decode()
        if msg['cmd'] == IPRCMD_ACK:
            self._sctl_event.set()
        else:
            logging.error("got err for sctl, shutting down")
            # FIXME: shutdown all
            self._stop_event.set()

    def _feed_buffers(self):
        '''
        Background thread to feed reassembled buffers to the parser
        '''
        save_buffers = {}
        while True:
            (buf, marshal, sock) = self.buffers.get()
            if self._stop_event.is_set():
                return

            save = save_buffers.get(sock, None)
            if save is not None:
                # concatenate buffers
                buf.seek(0)
                save.write(buf.read())
                save.length += buf.length
                # discard save
                buf = save
                del save_buffers[sock]

            offset = 0
            while offset < buf.length:
                buf.seek(offset)
                length = struct.unpack('I', buf.read(4))[0]

                if offset + length > buf.length:
                    # create save buffer
                    buf.seek(offset)
                    save = io.BytesIO()
                    save.length = save.write(buf.read())
                    save_buffers[sock] = save
                    # truncate the buffer
                    buf.truncate(offset)
                    break

                if sock in self.clients:
                    # create masquerade record for client's messages
                    # 1. generate nonce
                    nonce = self.nonce()
                    # 2. save masquerade record, invalidating old one
                    buf.seek(offset + 8)
                    seq, pid = struct.unpack('II', buf.read(8))
                    self.masquerade[nonce] = masq_record(seq, pid, sock)
                    # 3. overwrite seq and pid
                    buf.seek(offset + 8)
                    buf.write(struct.pack('II', nonce, self.pid))

                buf.seek(offset)
                data = io.BytesIO()
                data.write(buf.read(length))
                data.length = length
                if sock in self.rtable:
                    # FIXME: catch exceptions level above
                    if self.rtable[sock](data):
                        try:
                            self.parse(data, marshal, sock)
                        except:
                            traceback.print_exc()

                offset += length

    def _expire_masq(self):
        '''
        Background thread that expires masquerade cache entries
        '''
        while True:
            # expire masquerade records
            ts = time.time()
            for i in tuple(self.masquerade.keys()):
                if (ts - self.masquerade[i].ctime) > 60:
                    del self.masquerade[i]
            self._stop_event.wait(60)
            if self._stop_event.is_set():
                return

    def nonce(self):
        with self._nonce_lock:
            if self._nonce == 0xffffffff:
                self._nonce = 1
            else:
                self._nonce += 1
            return self._nonce

    def distribute(self, data):
        """
        Send message to all clients. Called from self.route()
        """
        data.seek(8)
        # read sequence number and pid
        seq, pid = struct.unpack('II', data.read(8))
        # default target -- broadcast
        target = None
        # if it is a unicast response
        if pid == self.pid:
            # lookup masquerade table
            target = self.masquerade.get(seq, None)
        # there is valid masquerade record
        if target is not None:
            # fill up client's pid and seq
            offset = 0
            # ... but -- for each message in the packet :)
            while offset < data.length:
                # write the data
                data.seek(offset + 8)
                data.write(struct.pack('II', target.seq, target.pid))
                # skip to the next message
                data.seek(offset)
                length = struct.unpack('I', data.read(4))[0]
                offset += length

            target.socket.send(data.getvalue())
        else:
            # otherwise, broadcast packet
            for sock in self.broadcast:
                sock.send(data.getvalue())
            # return True -- this packet should be parsed
            return True

    def route(self, sock, data):
        """
        Route message
        """
        data.seek(4)
        # message type, offset 4 bytes, length 2 bytes
        mtype = struct.unpack('H', data.read(2))[0]
        # FIXME log routing failures

        ##
        #
        # NETLINK_UNUSED as intra-pyroute2
        #
        if (mtype == NETLINK_UNUSED) and (sock in self.controls):
            rsp = ctrlmsg()
            rsp['header']['type'] = NETLINK_UNUSED
            rsp['cmd'] = IPRCMD_ERR
            cmd = self.parse_control(data)
            if cmd['cmd'] == IPRCMD_STOP:
                # Last 'hello'
                rsp['cmd'] = IPRCMD_ACK
                rsp.encode()
                sock.send(rsp.buf.getvalue())
                # Stop iothread -- shutdown sequence
                self._stop_event.set()
                self._rlist.remove(self.sctl)
                self._wlist.remove(self.sctl)
                self.sctl.close()
                self.control.close()
                self.buffers.put((None, None, None))
                self._feed_thread.join()
                self._expire_thread.join()
                return
            elif cmd['cmd'] == IPRCMD_RELOAD:
                # Reload io cycle
                self._reload_event.set()
                rsp['cmd'] = IPRCMD_ACK
            rsp.encode()
            sock.send(rsp.buf.getvalue())

        ##
        #
        # NETLINK_UNUSED as inter-pyroute2
        #
        elif (mtype == NETLINK_UNUSED) and (sock in self.clients):
            rsp = ctrlmsg()
            rsp['header']['type'] = NETLINK_UNUSED
            rsp['cmd'] = IPRCMD_ERR
            cmd = self.parse_control(data)
            if cmd['cmd'] == IPRCMD_ROUTE:
                # routing request
                family = cmd.get_attr('CTRL_ATTR_FAMILY_ID')
                if family in self.families:
                    send = self.families[family]
                    self.rtable[sock] = send
                    self.broadcast.add(sock)
                    rsp['cmd'] = IPRCMD_ACK
                # TODO tags: remote
                #
                # * subscribe requests
                # * ...
            elif cmd['cmd'] == IPRCMD_REGISTER:
                # auth request
                secret = cmd.get_attr('IPR_ATTR_SECRET')
                if secret == self.secret:
                    self.controls.add(sock)
                    rsp['cmd'] = IPRCMD_ACK
            rsp.encode()
            sock.send(rsp.buf.getvalue())

        ##
        #
        # Data messages
        #
        else:
            self.buffers.put((data, self.marshals.get(sock, None), sock))

    def recv(self, fd, buf):
        ret = buf.write(fd.recv(16384))
        return ret, {}

    def send(self, buf):
        data = buf.getvalue()
        for sock in self.uplinks:
            if isinstance(sock, NetlinkSocket):
                sock.sendto(data, (0, 0))
            else:
                sock.send(data)

    def parse_control(self, data):
        data.seek(0)
        cmd = ctrlmsg(data)
        cmd.decode()
        return cmd

    def parse(self, data, marshal, sock):
        '''
        Parse and enqueue messages. A message can be
        retrieved from netlink socket as well as from a
        remote system, and it should be properly enqueued
        to make it available for Netlink.get() method.

        If IOThread.mirror is set, all messages will be also
        copied (mirrored) to the default 0 queue. Please
        make sure that 0 queue exists, before setting
        IOThread.mirror to True.

        If there is no such queue for received
        sequence_number, leave sequence_number intact, but
        put the message into default 0 queue, if it exists.
        '''

        for msg in marshal.parse(data):
            if self.record:
                self.backlog.append((time.asctime(), msg))
            key = msg['header']['sequence_number']
            try:
                msg['header']['host'] = _repr_sockets([sock], 'remote')[0]
            except socket.error:
                # on shutdown, we can get here socket.error
                # in this case add just an empty string
                msg['header']['host'] = ''

            # 8<--------------------------------------------------------------
            # message filtering
            # right now it is simply iterating callback list
            for cr in self.callbacks:
                if cr[0](msg):
                    cr[1](msg, *cr[2])

            # 8<--------------------------------------------------------------
            if key not in self.listeners:
                key = 0
            if self.mirror and (key != 0) and (msg.raw is not None):
                # On Python 2.6 it can fail due to class fabrics
                # in nlmsg definitions, so parse it again. It should
                # not be much slower than copy.deepcopy()
                try:
                    raw = io.BytesIO()
                    raw.length = raw.write(msg.raw)
                    self.listeners[0].put_nowait(marshal.parse(raw)[0])
                except Queue.Full:
                    # FIXME: log this
                    pass
            if key in self.listeners:
                try:
                    self.listeners[key].put_nowait(msg)
                except Queue.Full:
                    # FIXME: log this
                    pass

    def command(self, cmd, attrs=[]):
        msg = ctrlmsg(io.BytesIO())
        msg['header']['type'] = NETLINK_UNUSED
        msg['cmd'] = cmd
        msg['attrs'] = attrs
        msg.encode()
        self.control.send(msg.buf.getvalue())
        rsp = ctrlmsg(self.control.recv(256))
        rsp.decode()
        return rsp

    def stop(self):
        try:
            self.command(IPRCMD_STOP)
        except OSError:
            pass

    def reload(self):
        '''
        Reload I/O cycle. Warning: this method should be never
        called from IOThread, as it will not return.
        '''
        self._reload_event.clear()
        ret = self.command(IPRCMD_RELOAD)
        # wait max 3 seconds for reload
        # FIXME: timeout should be configurable
        self._reload_event.wait(3)
        assert self._reload_event.is_set()
        return ret

    def add_server(self, url):
        '''
        Add a server socket to listen for clients on
        '''
        (sock, address) = _get_socket(url, server_side=True,
                                      ssl_keys=self.ssl_keys)
        if sock.family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(address)
        sock.listen(16)
        self._rlist.add(sock)
        self.servers.add(sock)
        self.reload()
        return sock

    def remove_server(self, sock=None, address=None):
        assert sock or address
        if address:
            for sock in self.servers:
                if sock.getsockname() == address:
                    break
        assert sock
        self._rlist.remove(sock)
        self.servers.remove(sock)
        self.reload()
        return sock

    def add_uplink(self, sock, marshal):
        self._rlist.add(sock)
        self.uplinks.add(sock)
        self.rtable[sock] = self.distribute
        self.marshals[sock] = marshal()
        self.reload()
        return sock

    def remove_uplink(self, sock):
        self._rlist.remove(sock)
        self.uplinks.remove(sock)
        del self.rtable[sock]
        del self.marshals[sock]
        self.reload()
        return sock

    def add_client(self, sock):
        '''
        Add a client connection. Should not be called
        manually, but only on a client connect.
        '''
        self._rlist.add(sock)
        self._wlist.add(sock)
        self.clients.add(sock)
        return sock

    def remove_client(self, sock):
        self._rlist.remove(sock)
        self._wlist.remove(sock)
        self.clients.remove(sock)
        if sock in self.broadcast:
            self.broadcast.remove(sock)
        return sock

    def start(self):
        threading.Thread.start(self)
        self._sctl_event.wait(3)
        self._sctl_thread.join()
        if not self._sctl_event.is_set():
            self._stop_event.set()
            raise RuntimeError('failed to establish control connection')

    def run(self):
        self._run_event.set()
        while not self._stop_event.is_set():
            try:
                [rlist, wlist, xlist] = select.select(self._rlist, [], [])
            except:
                # FIXME: log exceptions
                continue
            for fd in rlist:

                ##
                #
                # Incoming remote connections
                #
                if fd in self.servers:
                    try:
                        (client, addr) = fd.accept()
                        self.add_client(client)
                    except ssl.SSLError:
                        # FIXME log SSL errors
                        pass
                    except:
                        traceback.print_exc()
                    continue

                ##
                #
                # Receive data from already open connection
                #
                # FIXME max length
                data = io.BytesIO()
                try:
                    # recv method
                    recv = self.recv_methods.get(fd, self.recv)
                    # fill the routing info and get the data
                    data.length, rinfo = recv(fd, data)
                except:
                    traceback.print_exc()
                    continue

                ##
                #
                # Close socket
                #
                if data.length == 0:
                    if fd in self.clients:
                        self.remove_client(fd)
                    elif fd in self.uplinks:
                        self.remove_uplink(fd)
                    continue

                ##
                #
                # Route the data
                #
                if self.record:
                    self.backlog.append((time.asctime(),
                                         fd.getsockname(),
                                         data))
                self.route(fd, data)


class Netlink(object):
    '''
    Main netlink messaging class. It automatically spawns threads
    to monitor network and netlink I/O, creates and destroys message
    queues.

    By default, netlink class connects to the local netlink socket
    on startup. If you prefer to connect to another host, use::

        nl = Netlink(host='tcp://remote.01host:7000')

    It is possible to connect to uplinks after the startup::

        nl = Netlink(do_connect=False)
        nl.connect('tcp://remote.01host:7000')

    To act as a server, call serve()::

        nl = Netlink(do_connect=False)
        nl.connect('localsystem')
        nl.serve('unix:///tmp/pyroute')
    '''

    family = NETLINK_GENERIC
    groups = 0
    marshal = Marshal

    def __init__(self, debug=False, timeout=3, do_connect=True,
                 host='localsystem', key=None, cert=None, ca=None):
        self._timeout = timeout
        self.iothread = IOThread()
        self.listeners = self.iothread.listeners
        self.ssl_keys = self.iothread.ssl_keys
        self._sockets = set()
        self.servers = {}
        self.iothread.families[self.family] = self.iothread.send
        self.iothread.start()
        self.debug = debug
        self.marshal.debug = debug
        if do_connect:
            self.connect(host, key, cert, ca)

    def _remote_cmd(self, sock, cmd, attrs=None):
        attrs = attrs or []
        smsg = ctrlmsg()
        smsg['header']['type'] = NETLINK_UNUSED
        smsg['header']['pid'] = os.getpid()
        smsg['cmd'] = cmd
        smsg['attrs'] = attrs
        smsg.encode()
        sock.send(smsg.buf.getvalue())

    def connect(self,
                host='localsystem',
                key=None,
                cert=None,
                ca=None,
                **kwarg):
        assert isinstance(host, basestring)
        sock = None
        if key:
            self.ssl_keys[host] = ssl_credentials(key, cert, ca)
        try:
            if host == 'localsystem':
                sock = NetlinkSocket(self.family)
                sock.bind(self.groups)
            else:
                try:
                    # built-in connection types
                    (sock, addr) = _get_socket(url=host,
                                               server_side=False,
                                               ssl_keys=self.ssl_keys)
                    sock.connect(addr)
                except AssertionError:
                    # try to load a plugin
                    (ctype, create, command) = _get_plugin(host)
                    if ctype == 'queue':
                        nonce = self.iothread.nonce()
                        self.listeners[nonce] = create(command,
                                                       self.marshal,
                                                       **kwarg)
                        return nonce
                    else:
                        raise Exception('plugin not supported')

                self._remote_cmd(sock=sock,
                                 cmd=IPRCMD_ROUTE,
                                 attrs=[['CTRL_ATTR_FAMILY_ID',
                                         self.family]])
                rsp = ctrlmsg(sock.recv(28))
                rsp.decode()
                assert rsp['cmd'] == IPRCMD_ACK
        except Exception as e:
            if host in self.ssl_keys:
                del self.ssl_keys[host]
            raise e
        else:
            self.iothread.add_uplink(sock, self.marshal)
            self._sockets.add(sock)

    def get_servers(self):
        return _repr_sockets(self.iothread.servers, 'local')

    def get_clients(self):
        return _repr_sockets(self.iothread.clients, 'remote')

    def get_sockets(self):
        return _repr_sockets(self._sockets, 'remote')

    def shutdown_servers(self, *urls):
        self._shutdown_sockets([i for i in self.iothread.servers
                                if _repr_sockets([i], 'local') !=
                                _repr_sockets([self.iothread.sctl], 'local')],
                               'local', self.iothread.remove_server, *urls)

    def shutdown_clients(self, *urls):
        self._shutdown_sockets([i for i in self.iothread.clients
                                if _repr_sockets([i], 'remote') !=
                                _repr_sockets([self.iothread.sctl], 'remote')],
                               'remote', self.iothread.remove_client, *urls)

    def shutdown_sockets(self, *urls):
        self._shutdown_sockets(self._sockets, 'remote',
                               self.iothread.remove_uplink, *urls)

    def _shutdown_sockets(self, sockets, way, func, *urls):
        for sock in tuple(sockets):
            if (_repr_sockets([sock], way)[0] in urls) or not urls:
                sock.close()
                sockets.remove(sock)
                try:
                    func(sock)
                except:
                    pass

    def release(self):
        '''
        Shutdown all threads and release netlink sockets
        '''
        self.shutdown_sockets()
        self.shutdown_clients()
        self.shutdown_servers()
        self.iothread.stop()
        self.iothread.join()

    def serve(self, url, key=None, cert=None, ca=None):
        if key:
            self.ssl_keys[url] = ssl_credentials(key, cert, ca)
        self.servers[url] = self.iothread.add_server(url)

    def mirror(self, operate=True):
        '''
        Turn message mirroring on/off. When it is 'on', all
        received messages will be copied (mirrored) into the
        default 0 queue.
        '''
        self.monitor(operate)
        self.iothread.mirror = operate

    def monitor(self, operate=True):
        '''
        Create/destroy the default 0 queue. Netlink socket
        receives messages all the time, and there are many
        messages that are not replies. They are just
        generated by the kernel as a reflection of settings
        changes. To start receiving these messages, call
        Netlink.monitor(). They can be fetched by
        Netlink.get(0) or just Netlink.get().
        '''
        if operate:
            self.listeners[0] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
        else:
            del self.listeners[0]

    def register_callback(self, callback, predicate=lambda x: True, args=None):
        '''
        Register a callback to run on a message arrival.

        Callback is the function that will be called with the
        message as the first argument. Predicate is the optional
        callable object, that returns True or False. Upon True,
        the callback will be called. Upon False it will not.
        Args is a list or tuple of arguments.

        Simplest example, assume ipr is the IPRoute() instance::

            # create a simplest callback that will print messages
            def cb(msg):
                print(msg)

            # register callback for any message:
            ipr.register_callback(cb)

        More complex example, with filtering::

            # Set object's attribute after the message key
            def cb(msg, obj):
                obj.some_attr = msg["some key"]

            # Register the callback only for the loopback device, index 1:
            ipr.register_callback(cb,
                                  lambda x: x.get('index', None) == 1,
                                  (self, ))

        Please note: you do **not** need to register the default 0 queue
        to invoke callbacks on broadcast messages. Callbacks are
        iterated **before** messages get enqueued.
        '''
        if args is None:
            args = []
        self.iothread.callbacks.append((predicate, callback, args))

    def unregister_callback(self, callback):
        '''
        Remove the first reference to the function from the callback
        register
        '''
        cb = tuple(self.iothread.callbacks)
        for cr in cb:
            if cr[1] == callback:
                self.iothread.callbacks.pop(cb.index(cr))
                return

    def _remove_queue(self, key):
        '''
        Flush the queue to the default one and remove it
        '''
        queue = self.listeners[key]
        # only not the default queue
        if key != 0:
            # delete the queue
            del self.listeners[key]
            # get remaining messages from the queue and
            # re-route them to queue 0 or drop
            while not queue.empty():
                msg = queue.get()
                if 0 in self.listeners:
                    self.listeners[0].put(msg)

    def get(self, key=0, raw=False):
        '''
        Get a message from a queue

        * key -- message queue number
        '''
        queue = self.listeners[key]
        result = []
        hosts = len(self._sockets)
        while True:
            # timeout should alse be set to catch ctrl-c
            # Bug-Url: http://bugs.python.org/issue1360
            try:
                msg = queue.get(block=True, timeout=self._timeout)
            except Queue.Empty as e:
                if key == 0 or hasattr(queue, 'persist'):
                    continue
                self._remove_queue(key)
                raise e
            # terminator for persisten queues
            if msg is None:
                self._remove_queue(key)
                raise Queue.Empty()
            if (msg['header']['error'] is not None) and (not raw):
                self._remove_queue(key)
                raise msg['header']['error']
            if (msg['header']['type'] != NLMSG_DONE) or raw:
                result.append(msg)
            if (msg['header']['type'] == NLMSG_DONE) or \
               (not msg['header']['flags'] & NLM_F_MULTI):
                hosts -= 1
            if hosts == 0 or raw:
                break
        if not hasattr(queue, 'persist'):
            self._remove_queue(key)
        return result

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST):
        '''
        Send netlink request, filling common message
        fields, and wait for response.
        '''
        # FIXME make it thread safe, yeah
        nonce = self.iothread.nonce()
        self.listeners[nonce] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg.encode()
        self.iothread.send(msg.buf)
        result = self.get(nonce)
        if not self.debug:
            for i in result:
                del i['header']
        return result
