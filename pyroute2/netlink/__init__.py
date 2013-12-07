import traceback
import threading
import logging
import select
import struct
import socket
import time
import os
import io
import uuid
import ssl
import sys

from pyroute2.netlink.generic import ctrlmsg
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import envmsg
from pyroute2.netlink.generic import NetlinkDecodeError
from pyroute2.netlink.generic import NetlinkHeaderDecodeError
from pyroute2.netlink.generic import NETLINK_GENERIC
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

try:
    import Queue
except ImportError:
    import queue as Queue

_QUEUE_MAXSIZE = 4096

REALM_NONE = 0x0
REALM_DEFAULT = 0x10001
MASK_DEFAULT = 0xffff0000

C_ADDR_START = 3


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
NLMSG_CONTROL = 0xe    # Custom message type for messaging control
NLMSG_TRANSPORT = 0xf    # Custom message type for NL as a transport
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
IPRCMD_CONNECT = 7
IPRCMD_DISCONNECT = 8
IPRCMD_SERVE = 9
IPRCMD_SHUTDOWN = 10
IPRCMD_SUBSCRIBE = 11
IPRCMD_UNSUBSCRIBE = 12


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

        sname = i.getsockname()
        if i.family == socket.AF_UNIX:
            if sys.version[0] == '3':
                sname = sname.decode('utf-8')
            url += '://%s' % (sname)
        elif i.family == AF_PIPE:
            url += '://%i,%i' % (sname)
        else:
            if mode == 'local':
                url += '://%s:%i' % (sname)
            elif mode == 'remote':
                url += '://%s:%i' % (sname)
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


class Layer(object):

    def __init__(self, raw):
        if isinstance(raw, nlmsg):
            self.length = raw['header']['length']
            self.mtype = raw['header']['type']
            self.flags = raw['header']['flags']
            self.nonce = raw['header']['sequence_number']
            self.pid = raw['header']['pid']
        else:
            init = raw.tell()
            (self.length,
             self.mtype,
             self.flags,
             self.nonce,
             self.pid) = struct.unpack('IHHII', raw.read(16))
            raw.seek(init)


class MasqRecord(object):

    def __init__(self, dst, src, socket):
        self.src = src
        self.dst = dst
        self.envelope = None
        self.data = None
        self.socket = socket
        self.ctime = time.time()

    def add_envelope(self, envelope):
        self.envelope = Layer(envelope)

    def add_data(self, data):
        self.data = Layer(data)


class IOThread(threading.Thread):
    def __init__(self,
                 addr=0x01000000,
                 mask=0xff000000,
                 sys_mask=0x00ff0000,
                 con_mask=0x0000ffff):
        threading.Thread.__init__(self, name='Netlink I/O core')
        #self.setDaemon(True)
        self.pid = os.getpid()
        self._nonce = 0
        self._nonce_lock = threading.Lock()
        self._addr_lock = threading.Lock()
        self._run_event = threading.Event()
        self._sctl_event = threading.Event()
        self._stop_event = threading.Event()
        self._reload_event = threading.Event()
        # new address scheme
        self.addr = addr
        self.mask = mask
        self.sys_mask = sys_mask
        self.con_mask = con_mask
        self.default_sys = {'netlink': 0x00010000,
                            'tcp': 0x00010000,
                            'unix': 0x00010000}
        self.active_sys = {}
        self.active_conn = {}
        # fd lists for select()
        self._rlist = set()
        self._wlist = set()
        self._xlist = set()
        # routing
        self.xtable = {}          # {(realm, mask): socket, ...}
        self.marshals = {}        # {netlink_socket: marshal, ...}
        self.listeners = {}       # {int: Queue(), int: Queue()...}
        self.masquerade = {}      # {int: MasqRecord()...}
        self.recv_methods = {}    # {socket: recv_method, ...}
        self.clients = set()      # set(socket, socket...)
        self.uplinks = set()      # set(socket, socket...)
        self.servers = set()      # set(socket, socket...)
        self.controls = set()     # set(socket, socket...)
        self.ssl_keys = {}        # {url: ssl_credentials(), url:...}
        self.subscribe = {}
        self._cids = list(range(1024))
        # secret; write non-zero byte as terminator
        self.secret = os.urandom(15)
        self.secret += b'\xff'
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
        #self._expire_thread.setDaemon(True)
        self._expire_thread.start()

    def alloc_cid(self):
        try:
            return self._cids.pop()
        except IndexError:
            return None

    def dealloc_cid(self, cid):
        self._cids.append(cid)

    def alloc_addr(self, system, block=False):
        with self._addr_lock:
            if system not in self.active_sys:
                self.active_sys[system] = list(range(C_ADDR_START,
                                                     self.con_mask - 1))
            return system | self.active_sys[system].pop(0)

    def dealloc_addr(self, addr):
        with self._addr_lock:
            system = addr & self.sys_mask
            local = addr & self.con_mask
            self.active_sys[system].append(local)

    def _sctl(self):
        msg = ctrlmsg()
        msg['header']['type'] = NLMSG_CONTROL
        msg['cmd'] = IPRCMD_REGISTER
        msg['attrs'] = [['IPR_ATTR_SECRET', self.secret]]
        msg.encode()
        envelope = envmsg()
        envelope['header']['type'] = NLMSG_TRANSPORT
        envelope['header']['flags'] = 1
        envelope['attrs'] = [['IPR_ATTR_CDATA', msg.buf.getvalue()]]
        envelope.encode()

        self._run_event.wait()
        self.control.send(envelope.buf.getvalue())

        buf = io.BytesIO()
        buf.write(self.control.recv())
        buf.seek(0)
        envelope = envmsg(buf)
        envelope.decode()
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        msg = ctrlmsg(data)
        msg.decode()
        if msg['cmd'] == IPRCMD_ACK:
            self._sctl_event.set()
        else:
            logging.error("got err for sctl, shutting down")
            # FIXME: shutdown all
            self._stop_event.set()

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

    def route_control(self, sock, data):
        # open envelope
        envelope = self.parse_envelope(data)
        pid = envelope['header']['pid']
        nonce = envelope['header']['sequence_number']
        src = envelope['src']
        dst = envelope['dst']
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        cmd = self.parse_control(data)
        rsp = ctrlmsg()
        rsp['header']['type'] = NLMSG_CONTROL
        rsp['header']['sequence_number'] = nonce
        rsp['cmd'] = IPRCMD_ERR
        rsp['attrs'] = []

        if sock in self.controls:
            if cmd['cmd'] == IPRCMD_STOP:
                # Last 'hello'
                rsp['cmd'] = IPRCMD_ACK
                rsp.encode()
                ne = envmsg()
                ne['header']['sequence_number'] = nonce
                ne['header']['pid'] = pid
                ne['header']['type'] = NLMSG_TRANSPORT
                ne['header']['flags'] = 1
                ne['dst'] = src
                ne['src'] = dst
                ne['attrs'] = [['IPR_ATTR_CDATA', rsp.buf.getvalue()]]
                ne.encode()
                sock.send(ne.buf.getvalue())
                # Stop iothread -- shutdown sequence
                self._stop_event.set()
                self._rlist.remove(self.sctl)
                self._wlist.remove(self.sctl)
                self.sctl.close()
                self.control.close()
                self._expire_thread.join()
                return

            elif cmd['cmd'] == IPRCMD_RELOAD:
                # Reload io cycle
                self._reload_event.set()
                rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_SERVE:
                url = cmd.get_attr('IPR_ATTR_HOST')
                (new_sock, addr) = _get_socket(url, server_side=True,
                                               ssl_keys=self.ssl_keys)
                new_sock.bind(addr)
                new_sock.listen(16)
                self._rlist.add(new_sock)
                self.servers.add(new_sock)
                self._reload_event.set()
                rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_SHUTDOWN:
                url = cmd.get_attr('IPR_ATTR_HOST')
                for old_sock in self.servers:
                    if _repr_sockets([old_sock]) == [url]:
                        self._rlist.remove(old_sock)
                        self.servers.remove(old_sock)
                        self._reload_event.set()
                        rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_DISCONNECT:
                # drop a connection, identified by an addr
                try:
                    addr = cmd.get_attr('IPR_ATTR_ADDR')
                    self.deregister_link(addr)
                    rsp['cmd'] = IPRCMD_ACK
                    self._reload_event.set()
                except Exception as e:
                    rsp['attrs'] = [['IPR_ATTR_ERROR', str(e)]]

            elif cmd['cmd'] == IPRCMD_CONNECT:
                # connect to a system
                try:
                    url = cmd.get_attr('IPR_ATTR_HOST')
                    target = urlparse.urlparse(url)
                    if target.scheme == 'netlink':
                        new_sock = NetlinkSocket(int(target.hostname))
                        new_sock.bind(int(target.port))
                        sys = cmd.get_attr('IPR_ATTR_SYS',
                                           self.default_sys[target.scheme])
                        send = lambda d, s:\
                            new_sock.sendto(self.gate_untag(d, s), (0, 0))
                        addr = self.alloc_addr(sys)
                        rsp['attrs'].append(['IPR_ATTR_ADDR', addr])
                        self.register_link(addr, new_sock, send)
                        rsp['cmd'] = IPRCMD_ACK
                        self._reload_event.set()
                    else:
                        (new_sock, addr) = _get_socket(url,
                                                       server_side=False,
                                                       ssl_keys=self.ssl_keys)
                        new_sock.connect(addr)
                        sys = cmd.get_attr('IPR_ATTR_SYS',

                                           self.default_sys[target.scheme])
                        send = lambda d, s:\
                            new_sock.send(self.gate_forward(d, s))
                        addr = self.alloc_addr(sys)
                        rsp['attrs'].append(['IPR_ATTR_ADDR', addr])
                        self.register_link(addr, new_sock, send)
                        rsp['cmd'] = IPRCMD_ACK
                        self._reload_event.set()
                except Exception as e:
                    rsp['attrs'].append(['IPR_ATTR_ERROR',
                                         traceback.format_exc()])
        if sock in self.clients:
            if cmd['cmd'] == IPRCMD_SUBSCRIBE:
                cid = self.alloc_cid()
                if cid is not None:
                    self.subscribe[cid] = {'socket': sock,
                                           'keys': []}
                    for key in cmd.get_attrs('IPR_ATTR_KEY'):
                        target = (key['offset'],
                                  key['key'],
                                  key['mask'])
                        self.subscribe[cid]['keys'].append(target)
                    rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_UNSUBSCRIBE:
                cid = cmd.get_attr('IPR_ATTR_CID')
                if cid in self.subscribe:
                    del self.subscribe[cid]
                    self.dealloc_cid()
                    rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_REGISTER:
                # auth request
                secret = cmd.get_attr('IPR_ATTR_SECRET')
                if secret == self.secret:
                    self.controls.add(sock)
                    rsp['cmd'] = IPRCMD_ACK

        rsp.encode()
        ne = envmsg()
        ne['header']['sequence_number'] = nonce
        ne['header']['pid'] = pid
        ne['header']['type'] = NLMSG_TRANSPORT
        ne['header']['flags'] = 1
        ne['dst'] = src
        ne['src'] = dst
        ne['attrs'] = [['IPR_ATTR_CDATA', rsp.buf.getvalue()]]
        ne.encode()
        sock.send(ne.buf.getvalue())

    def route_data(self, sock, data):
        envelope = self.parse_envelope(data)
        nonce = envelope['header']['sequence_number']
        if envelope['dst'] in self.active_conn:
            self.active_conn[envelope['dst']]['send'](envelope, sock)

        elif nonce in self.masquerade:
            target = self.masquerade[nonce]
            data.seek(8)
            data.write(struct.pack('II',
                                   target.envelope.nonce,
                                   target.envelope.pid))
            target.socket.send(data.getvalue())

        else:
            # unknown destination
            pass
            # rsp = ctrlmsg()
            # rsp['header']['type'] = NLMSG_CONTROL
            # rsp['cmd'] = IPRCMD_ERR
            # rsp['attrs'] = [['IPR_ATTR_ERROR',
            #                  'unknown destination']]
            # rsp.encode()
            # sock.send(rsp.buf.getvalue())

    def filter_u32(self, u32, data):
        for offset, key, mask in u32['keys']:
            data.seek(offset)
            compare = struct.unpack('I', data.read(4))[0]
            if compare & mask != key:
                return
        # envelope data
        envelope = envmsg()
        envelope['header']['type'] = NLMSG_TRANSPORT
        envelope['attrs'] = [['IPR_ATTR_CDATA',
                              data.getvalue()]]
        envelope.encode()
        u32['socket'].send(envelope.buf.getvalue())

    def route_local(self, sock, data, seq):
        # extract masq info
        target = self.masquerade.get(seq, None)
        if target is None:
            for cid, u32 in self.subscribe.items():
                self.filter_u32(u32, data)
        else:
            offset = 0
            while offset < data.length:
                data.seek(offset)
                (length,
                 mtype,
                 flags,
                 seq,
                 pid) = struct.unpack('IHHII', data.read(16))
                data.seek(offset + 8)
                data.write(struct.pack('II',
                                       target.data.nonce,
                                       target.data.pid))
                # skip to the next in chunk
                offset += length
            # envelope data
            envelope = envmsg()
            envelope['header']['sequence_number'] = target.envelope.nonce
            envelope['header']['pid'] = target.envelope.pid
            envelope['header']['type'] = NLMSG_TRANSPORT
            envelope['dst'] = target.src
            envelope['src'] = target.dst
            envelope['attrs'] = [['IPR_ATTR_CDATA',
                                  data.getvalue()]]
            envelope.encode()
            # target
            target.socket.send(envelope.buf.getvalue())

    def route(self, sock, data):
        """
        Route message
        """
        data.seek(0)
        (length,
         mtype,
         flags,
         seq,
         pid) = struct.unpack('IHHII', data.read(16))

        if mtype == NLMSG_TRANSPORT:
            if flags == 1:
                return self.route_control(sock, data)
            else:
                return self.route_data(sock, data)
        else:
            return self.route_local(sock, data, seq)

    def recv(self, fd, buf):
        ret = 0
        ret += buf.write(fd.recv(16384))
        return ret, {}

    def gate_forward(self, envelope, sock):
        # 1. get data
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        # 2. register way back
        nonce = self.nonce()
        src = envelope['src']
        dst = envelope['dst']
        masq = MasqRecord(dst, src, sock)
        masq.add_envelope(envelope)
        masq.add_data(data)
        self.masquerade[nonce] = masq
        self.active_conn[envelope['dst']]['sroute'][nonce] = masq
        envelope['header']['sequence_number'] = nonce
        envelope['header']['pid'] = os.getpid()
        envelope.buf.seek(0)
        envelope.encode()
        # 3. return data
        return envelope.buf.getvalue()

    def gate_untag(self, envelope, sock):
        # 1. get data
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        # 2. register way back
        nonce = self.nonce()
        src = envelope['src']
        dst = envelope['dst']
        masq = MasqRecord(dst, src, sock)
        masq.add_envelope(envelope)
        masq.add_data(data)
        self.masquerade[nonce] = masq
        self.active_conn[envelope['dst']]['sroute'][nonce] = masq
        data.seek(8)
        data.write(struct.pack('II', nonce, self.pid))
        # 3. return data
        return data.getvalue()

    def parse_envelope(self, data):
        data.seek(0)
        envelope = envmsg(data)
        envelope.decode()
        return envelope

    def parse_control(self, data):
        data.seek(0)
        cmd = ctrlmsg(data)
        cmd.decode()
        return cmd

    def command(self, cmd, attrs=[]):
        msg = ctrlmsg(io.BytesIO())
        msg['header']['type'] = NLMSG_CONTROL
        msg['cmd'] = cmd
        msg['attrs'] = attrs
        msg.encode()
        envelope = envmsg()
        envelope['header']['type'] = NLMSG_TRANSPORT
        envelope['header']['flags'] = 1
        envelope['attrs'] = [['IPR_ATTR_CDATA', msg.buf.getvalue()]]
        envelope.encode()
        self.control.send(envelope.buf.getvalue())
        envelope = envmsg(self.control.recv())
        envelope.decode()
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        rsp = ctrlmsg(data)
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

    def register_link(self, addr, sock, send):
        self._rlist.add(sock)
        self.active_conn[addr] = {'sock': sock,
                                  'send': send,
                                  'sroute': {}}
        return sock

    def deregister_link(self, addr):
        sock = self.active_conn[addr]['sock']
        sock.close()
        self._rlist.remove(sock)
        del self.active_conn[addr]

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
                try:
                    self.route(fd, data)
                except Exception:
                    # FIXME: silently drop all exceptions yet
                    pass


class Netlink(threading.Thread):
    '''
    Main netlink messaging class. It automatically spawns threads
    to monitor network and netlink I/O, creates and destroys message
    queues.

    By default, netlink class connects to the local netlink socket
    on startup. If you prefer to connect to another host, use::

        nl = Netlink(host='tcp://remote.host:7000')

    It is possible to connect to uplinks after the startup::

        nl = Netlink(do_connect=False)
        nl.connect('tcp://remote.host:7000')

    To act as a server, call serve()::

        nl = Netlink()
        nl.serve('unix:///tmp/pyroute')
    '''

    family = NETLINK_GENERIC
    groups = 0
    marshal = Marshal

    def __init__(self, debug=False, timeout=3000, do_connect=True,
                 host=None, key=None, cert=None, ca=None):
        threading.Thread.__init__(self, name='Netlink API')
        self._timeout = timeout
        self.iothread = IOThread()
        self.default_realm = 0
        self.realms = set()     # set(addr, addr, ...)
        self.listeners = {}     # {nonce: Queue(), ...}
        self.callbacks = []     # [(predicate, callback, args), ...]
        self.debug = debug
        self.marshal.debug = debug
        self.marshal = self.marshal()
        self.buffers = Queue.Queue()
        self.mirror = False
        self.host = host or 'netlink://%i:%i' % (self.family, self.groups)
        self._run_event = threading.Event()
        self._stop_event = threading.Event()
        self._feed_thread = threading.Thread(target=self._feed_buffers,
                                             name='Reasm and parsing')
        #self._feed_thread.setDaemon(True)
        self._feed_thread.start()
        #self.setDaemon(True)
        self.start()
        self._run_event.wait()
        if do_connect:
            self.default_realm = self.connect()

    def run(self):
        # 1. run iothread
        self.iothread.start()
        # 2. connect to iothread
        self._brs, self.bridge = pairPipeSockets()
        #import rpdb2
        #rpdb2.start_embedded_debugger("bala")
        self.iothread.add_client(self._brs)
        self.iothread.reload()

        msg = ctrlmsg()
        msg['header']['type'] = NLMSG_CONTROL
        msg['cmd'] = IPRCMD_REGISTER
        msg['attrs'] = [['IPR_ATTR_SECRET', self.iothread.secret]]
        msg.encode()
        envelope = envmsg()
        envelope['header']['type'] = NLMSG_TRANSPORT
        envelope['header']['flags'] = 1
        envelope['attrs'] = [['IPR_ATTR_CDATA', msg.buf.getvalue()]]
        envelope.encode()

        self.bridge.send(envelope.buf.getvalue())
        # assume iothread is up and running...
        buf = io.BytesIO()
        buf.write(self.bridge.recv())
        buf.seek(0)

        envelope = envmsg(buf)
        envelope.decode()
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        msg = ctrlmsg(data)
        msg.decode()

        if msg['cmd'] == IPRCMD_ACK:
            self._run_event.set()
        else:
            return

        # 3. start to monitor it
        while not self._stop_event.is_set():
            try:
                [rlist, wlist, xlist] = select.select([self.bridge], [], [])
            except:
                continue
            for fd in rlist:
                data = io.BytesIO()
                try:
                    data = fd.recv()
                except:
                    continue

                # put data in the queue
                self.buffers.put(data)

    def _feed_buffers(self):
        '''
        Background thread to feed reassembled buffers to the parser
        '''
        save = None
        while True:
            buf = io.BytesIO()
            buf.length = buf.write(self.buffers.get())
            if self._stop_event.is_set():
                return

            buf.seek(0)

            if save is not None:
                # concatenate buffers
                buf.seek(0)
                save.write(buf.read())
                save.length += buf.length
                # discard save
                buf = save
                save = None

            offset = 0
            while offset < buf.length:
                buf.seek(offset)
                (length,
                 mtype,
                 flags) = struct.unpack('IHH', buf.read(8))

                if offset + length > buf.length:
                    # create save buffer
                    buf.seek(offset)
                    save = io.BytesIO()
                    save.length = save.write(buf.read())
                    # truncate the buffer
                    buf.truncate(offset)
                    break

                buf.seek(offset)
                data = io.BytesIO()
                data.write(buf.read(length))
                data.length = length
                data.seek(0)

                # data traffic
                envelope = envmsg(data)
                envelope.decode()
                nonce = envelope['header']['sequence_number']
                try:
                    buf = io.BytesIO()
                    buf.length = buf.write(envelope.
                                           get_attr('IPR_ATTR_CDATA'))
                    buf.seek(0)
                    if flags == 1:
                        msg = ctrlmsg(buf)
                        msg.decode()
                        self.listeners[nonce].put_nowait(msg)
                    else:
                        self.parse(buf)
                except AttributeError:
                    # now silently drop bad packet
                    pass

                offset += length

    def parse(self, data):

        for msg in self.marshal.parse(data):
            key = msg['header']['sequence_number']

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
                    self.listeners[0].put_nowait(self.marshal.parse(raw)[0])
                except Queue.Full:
                    # FIXME: log this
                    pass

            if key in self.listeners:
                try:
                    self.listeners[key].put_nowait(msg)
                except Queue.Full:
                    # FIXME: log this
                    pass

    def command(self, cmd, attrs=[], expect=None):
        msg = ctrlmsg(io.BytesIO())
        msg['cmd'] = cmd
        msg['attrs'] = attrs
        rsp = self.nlm_request(msg, NLMSG_CONTROL, 0, 1)[0]
        assert rsp['cmd'] == IPRCMD_ACK
        if expect is not None:
            return rsp.get_attr(expect)
        else:
            return None

    def serve(self, url, key=None, cert=None, ca=None):
        return self.command(IPRCMD_SERVE,
                            [['IPR_ATTR_HOST', url]])

    def shutdown(self, url):
        return self.command(IPRCMD_SHUTDOWN,
                            [['IPR_ATTR_HOST', url]])

    def connect(self, host=None):
        if host is None:
            host = self.host
        realm = self.command(IPRCMD_CONNECT,
                             [['IPR_ATTR_HOST', host]],
                             expect='IPR_ATTR_ADDR')
        self.realms.add(realm)
        return realm

    def disconnect(self, realm):
        ret = self.command(IPRCMD_DISCONNECT,
                           [['IPR_ATTR_ADDR', realm]])
        self.realms.remove(realm)
        return ret

    def release(self):
        '''
        Shutdown all threads and release netlink sockets
        '''
        for realm in tuple(self.realms):
            self.disconnect(realm)
        self.iothread.stop()
        self.iothread.join()

        self._stop_event.set()
        self._brs.send("")
        self._brs.close()
        self.join()
        self.bridge.close()

        self.buffers.put("")
        self._feed_thread.join()

    def mirror(self, operate=True):
        '''
        Turn message mirroring on/off. When it is 'on', all
        received messages will be copied (mirrored) into the
        default 0 queue.
        '''
        self.monitor(operate)
        self.mirror = operate

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
            self.cid = self.command(IPRCMD_SUBSCRIBE,
                                    [['IPR_ATTR_KEY', {'offset': 8,
                                                       'key': 0,
                                                       'mask': 0}]])
        else:
            self.command(IPRCMD_UNSUBSCRIBE,
                         [['IPR_ATTR_CID', self.cid]])
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
        self.callbacks.append((predicate, callback, args))

    def unregister_callback(self, callback):
        '''
        Remove the first reference to the function from the callback
        register
        '''
        cb = tuple(self.callbacks)
        for cr in cb:
            if cr[1] == callback:
                self.callbacks.pop(cb.index(cr))
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

    def get(self, key=0, raw=False, timeout=None):
        '''
        Get a message from a queue

        * key -- message queue number
        '''
        queue = self.listeners[key]
        result = []
        timeout = timeout or self._timeout
        while True:
            # timeout should also be set to catch ctrl-c
            # Bug-Url: http://bugs.python.org/issue1360
            try:
                msg = queue.get(block=True, timeout=timeout)
            except Queue.Empty as e:
                if key == 0 or hasattr(queue, 'persist'):
                    continue
                self._remove_queue(key)
                raise e
            # terminator for persistent queues
            if msg is None:
                self._remove_queue(key)
                raise Queue.Empty()
            if (msg['header'].get('error', None) is not None) and\
                    (not raw):
                self._remove_queue(key)
                raise msg['header']['error']
            if (msg['header']['type'] != NLMSG_DONE) or raw:
                result.append(msg)
            if (msg['header']['type'] == NLMSG_DONE) or \
               (not msg['header']['flags'] & NLM_F_MULTI):
                break
            if raw:
                break
        if not hasattr(queue, 'persist'):
            self._remove_queue(key)
        return result

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST,
                    env_flags=0,
                    realm=None,
                    response_timeout=None):
        '''
        Send netlink request, filling common message
        fields, and wait for response.
        '''
        # FIXME make it thread safe, yeah
        realm = realm or self.default_realm
        nonce = self.iothread.nonce()
        self.listeners[nonce] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg.encode()
        envelope = envmsg()
        envelope['header']['sequence_number'] = nonce
        envelope['header']['pid'] = os.getpid()
        envelope['header']['type'] = NLMSG_TRANSPORT
        envelope['header']['flags'] = env_flags
        envelope['dst'] = realm
        envelope['src'] = 0
        envelope['attrs'] = [['IPR_ATTR_CDATA', msg.buf.getvalue()]]
        envelope.encode()
        self.bridge.send(envelope.buf.getvalue())
        result = self.get(nonce, timeout=response_timeout)
        if not self.debug:
            for i in result:
                del i['header']
        return result
