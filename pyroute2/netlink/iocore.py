import traceback
import threading
import select
import socket
import struct
import time
import os
import io
import uuid
import sys
import ssl

from pyroute2.common import AF_PIPE
from pyroute2.netlink import NetlinkSocket
from pyroute2.netlink import NLMSG_NOOP
from pyroute2.netlink import NLMSG_CONTROL
from pyroute2.netlink import NLMSG_TRANSPORT
from pyroute2.netlink import IPRCMD_ERR
from pyroute2.netlink import IPRCMD_STOP
from pyroute2.netlink import IPRCMD_ACK
from pyroute2.netlink import IPRCMD_RELOAD
from pyroute2.netlink import IPRCMD_SERVE
from pyroute2.netlink import IPRCMD_SHUTDOWN
from pyroute2.netlink import IPRCMD_CONNECT
from pyroute2.netlink import IPRCMD_DISCONNECT
from pyroute2.netlink import IPRCMD_UNSUBSCRIBE
from pyroute2.netlink import IPRCMD_SUBSCRIBE
from pyroute2.netlink import IPRCMD_REGISTER
from pyroute2.netlink.generic import ctrlmsg
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import envmsg

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

try:
    import Queue
except ImportError:
    import queue as Queue
_QUEUE_MAXSIZE = 4096


C_ADDR_START = 3

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


def _get_socket(url, server_side=False,
                key=None, cert=None, ca=None):
    assert url[:6] in ('udp://', 'tcp://', 'ssl://', 'tls://') or \
        url[:11] in ('unix+ssl://', 'unix+tls://') or url[:7] == 'unix://'
    target = urlparse.urlparse(url)
    hostname = target.hostname or ''
    use_ssl = False
    ssl_version = 2

    if target.scheme[:4] == 'unix':
        if hostname and hostname[0] == '\0':
            address = hostname
        else:
            address = ''.join((hostname, target.path))
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    elif target.scheme[:3] == 'udp':
        address = (socket.gethostbyname(hostname), target.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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

        assert key and cert and ca

        sock = ssl.wrap_socket(sock,
                               keyfile=key,
                               certfile=cert,
                               ca_certs=ca,
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
            if i.type == socket.SOCK_DGRAM:
                url = 'udp'
            else:
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


class IOCore(threading.Thread):
    def __init__(self,
                 addr=0x01000000,
                 mask=0xff000000,
                 sys_mask=0x00ff0000,
                 con_mask=0x0000ffff):
        threading.Thread.__init__(self, name='Netlink I/O core')
        #self.setDaemon(True)
        self.pid = os.getpid()
        self._addr_lock = threading.Lock()
        self._run_event = threading.Event()
        self._sctl_event = threading.Event()
        self._stop_event = threading.Event()
        self._reload_event = threading.Event()
        self.sys_mask = sys_mask
        self.con_mask = con_mask
        self.default_sys = {'netlink': 0x00010000,
                            'tcp': 0x00010000,
                            'udp': 0x00010000,
                            'unix': 0x00010000,
                            'unix+ssl': 0x00010000,
                            'unix+tls': 0x00010000,
                            'ssl': 0x00010000,
                            'tls': 0x00010000}
        self.active_sys = {}
        self.active_conn = {}
        # fd lists for select()
        self._rlist = set()
        self._wlist = set()
        self._xlist = set()
        # routing
        self.masquerade = {}      # {int: MasqRecord()...}
        self.recv_methods = {}    # {socket: recv_method, ...}
        self.clients = set()      # set(socket, socket...)
        self.servers = set()      # set(socket, socket...)
        self.controls = set()     # set(socket, socket...)
        self.subscribe = {}
        self.queue = Queue.Queue(_QUEUE_MAXSIZE)
        self._cid = list(range(1024))
        self._nonce = list(range(0xffff))
        # secret; write non-zero byte as terminator
        self.secret = os.urandom(15)
        self.secret += b'\xff'
        self.uuid = uuid.uuid4()
        # control in-process communication only
        self.sctl, self.control = pairPipeSockets()
        self.add_client(self.sctl)
        self.controls.add(self.sctl)
        # masquerade cache expiration
        self._expire_thread = threading.Thread(target=self._expire_masq,
                                               name='Masquerade cache')
        #self._expire_thread.setDaemon(True)
        self._expire_thread.start()
        self._dequeue_thread = threading.Thread(target=self._dequeue,
                                                name='Buffer queue')
        self._dequeue_thread.start()

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

    def _dequeue(self):
        '''
        Background thread that serves the buffer
        '''
        while not self._stop_event.is_set():
            try:
                self.route(*self.queue.get())
            except:
                pass

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
                    self._nonce.append(i)
            self._stop_event.wait(60)
            if self._stop_event.is_set():
                return

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
                self.queue.put(None)
                self.control.send(struct.pack('I', 4))
                return

            elif cmd['cmd'] == IPRCMD_RELOAD:
                # Reload io cycle
                self._reload_event.set()
                rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_SERVE:
                url = cmd.get_attr('IPR_ATTR_HOST')
                key = cmd.get_attr('IPR_ATTR_SSL_KEY')
                cert = cmd.get_attr('IPR_ATTR_SSL_CERT')
                ca = cmd.get_attr('IPR_ATTR_SSL_CA')
                (new_sock, addr) = _get_socket(url, server_side=True,
                                               key=key,
                                               cert=cert,
                                               ca=ca)
                new_sock.bind(addr)
                if new_sock.type == socket.SOCK_STREAM:
                    new_sock.listen(16)
                    self.servers.add(new_sock)
                self._rlist.add(new_sock)
                self.noop()
                rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_SHUTDOWN:
                url = cmd.get_attr('IPR_ATTR_HOST')
                for old_sock in tuple(self.servers):
                    if _repr_sockets([old_sock], 'local') == [url]:
                        self._rlist.remove(old_sock)
                        self.servers.remove(old_sock)
                        self.noop()
                        rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_DISCONNECT:
                # drop a connection, identified by an addr
                try:
                    addr = cmd.get_attr('IPR_ATTR_ADDR')
                    self.deregister_link(addr)
                    rsp['cmd'] = IPRCMD_ACK
                    self.noop()
                except Exception as e:
                    rsp['attrs'] = [['IPR_ATTR_ERROR', str(e)]]

            elif cmd['cmd'] == IPRCMD_CONNECT:
                # connect to a system
                try:
                    url = cmd.get_attr('IPR_ATTR_HOST')
                    key = cmd.get_attr('IPR_ATTR_SSL_KEY')
                    cert = cmd.get_attr('IPR_ATTR_SSL_CERT')
                    ca = cmd.get_attr('IPR_ATTR_SSL_CA')
                    target = urlparse.urlparse(url)
                    if target.scheme == 'netlink':
                        new_sock = NetlinkSocket(int(target.hostname))
                        new_sock.bind(int(target.port))
                        sys = cmd.get_attr('IPR_ATTR_SYS',
                                           self.default_sys[target.scheme])
                        send = lambda d, s:\
                            new_sock.sendto(self.gate_untag(d, s), (0, 0))
                        realm = self.alloc_addr(sys)
                        rsp['attrs'].append(['IPR_ATTR_ADDR', realm])
                        self.register_link(realm, new_sock, send)
                        rsp['cmd'] = IPRCMD_ACK
                        self.noop()
                    elif target.scheme == 'udp':
                        (new_sock, addr) = _get_socket(url,
                                                       server_side=False)
                        sys = cmd.get_attr('IPR_ATTR_SYS',
                                           self.default_sys[target.scheme])
                        send = lambda d, s:\
                            new_sock.sendto(self.gate_forward(d, s), addr)
                        realm = self.alloc_addr(sys)
                        rsp['attrs'].append(['IPR_ATTR_ADDR', realm])
                        self.register_link(realm, new_sock, send)
                        rsp['cmd'] = IPRCMD_ACK
                        self.noop()
                        print("connected", addr, new_sock)
                    else:
                        (new_sock, addr) = _get_socket(url,
                                                       server_side=False,
                                                       key=key,
                                                       cert=cert,
                                                       ca=ca)
                        new_sock.connect(addr)
                        sys = cmd.get_attr('IPR_ATTR_SYS',

                                           self.default_sys[target.scheme])
                        send = lambda d, s:\
                            new_sock.send(self.gate_forward(d, s))
                        realm = self.alloc_addr(sys)
                        rsp['attrs'].append(['IPR_ATTR_ADDR', realm])
                        self.register_link(realm, new_sock, send)
                        rsp['cmd'] = IPRCMD_ACK
                        self.noop()
                except Exception:
                    rsp['attrs'].append(['IPR_ATTR_ERROR',
                                         traceback.format_exc()])
        if sock in self.clients:
            if cmd['cmd'] == IPRCMD_SUBSCRIBE:
                try:
                    cid = self._cid.pop()
                    self.subscribe[cid] = {'socket': sock,
                                           'keys': []}
                    for key in cmd.get_attrs('IPR_ATTR_KEY'):
                        target = (key['offset'],
                                  key['key'],
                                  key['mask'])
                        self.subscribe[cid]['keys'].append(target)
                    rsp['cmd'] = IPRCMD_ACK
                    rsp['attrs'].append(['IPR_ATTR_CID', cid])
                except Exception:
                    rsp['attrs'].append(['IPR_ATTR_ERROR',
                                         traceback.format_exc()])

            elif cmd['cmd'] == IPRCMD_UNSUBSCRIBE:
                cid = cmd.get_attr('IPR_ATTR_CID')
                if cid in self.subscribe:
                    del self.subscribe[cid]
                    self._cid.append(cid)
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
            data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
            for cid, u32 in self.subscribe.items():
                self.filter_u32(u32, data)
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
        elif mtype == NLMSG_NOOP:
            return
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
        nonce = self._nonce.pop()
        src = envelope['src']
        dst = envelope['dst']
        masq = MasqRecord(dst, src, sock)
        masq.add_envelope(envelope)
        masq.add_data(data)
        self.masquerade[nonce] = masq
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
        nonce = self._nonce.pop()
        src = envelope['src']
        dst = envelope['dst']
        masq = MasqRecord(dst, src, sock)
        masq.add_envelope(envelope)
        masq.add_data(data)
        self.masquerade[nonce] = masq
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

    def noop(self):
        msg = ctrlmsg()
        msg['header']['type'] = NLMSG_NOOP
        msg.encode()
        self.control.send(msg.buf.getvalue())

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
        self.join()

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
                                  'send': send}
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

    def run(self):
        self._run_event.set()
        while not self._stop_event.is_set():
            try:
                [rlist, wlist, xlist] = select.select(self._rlist, [], [])
            except:
                # FIXME: log exceptions
                traceback.print_exc()
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
                    continue

                ##
                #
                # Route the data
                #
                try:
                    self.queue.put((fd, data))
                except Exception:
                    # FIXME: silently drop all exceptions yet
                    pass

        # shutdown sequence
        self._rlist.remove(self.sctl)
        self._wlist.remove(self.sctl)
        self.sctl.close()
        self.control.close()
        self._expire_thread.join()
        self._dequeue_thread.join()
