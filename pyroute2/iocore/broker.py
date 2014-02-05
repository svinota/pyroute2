import traceback
import threading
import socket
import struct
import errno
import time
import os
import io
import uuid
import sys
import ssl

from pyroute2.common import AF_PIPE
from pyroute2.netlink import Marshal
from pyroute2.netlink import NetlinkSocket
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
from pyroute2.netlink import IPRCMD_PROVIDE
from pyroute2.netlink import IPRCMD_REMOVE
from pyroute2.netlink import IPRCMD_DISCOVER
from pyroute2.netlink.generic import mgmtmsg
from pyroute2.netlink.generic import envmsg
from pyroute2.iocore import NLT_CONTROL
from pyroute2.iocore import NLT_RESPONSE
from pyroute2.iocore import NLT_DGRAM
from pyroute2.iocore.loop import IOLoop
from pyroute2.iocore.addrpool import AddrPool

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


C_ADDR_START = 3


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


def _get_socket(url, server=False,
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
                               server_side=server,
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


class Link(object):

    def __init__(self, uid, port, sock, keep, remote):
        self.uid = uid
        self.port = port
        self.sock = sock
        self.keep = keep
        self.remote = remote

    def gate(self, data, socket):
        pass


class Layer(object):

    def __init__(self, raw):
        init = raw.tell()
        (self.length,
         self.mtype,
         self.flags,
         self.nonce,
         self.pid) = struct.unpack('IHHII', raw.read(16))
        raw.seek(init)


class MasqRecord(object):

    def __init__(self, socket):
        self.envelope = None
        self.data = None
        self.socket = socket
        self.ctime = time.time()

    def add_envelope(self, envelope):
        self.envelope = envelope

    def add_data(self, data):
        self.data = Layer(data)


class MarshalEnv(Marshal):
    msg_map = {NLMSG_TRANSPORT: envmsg}


class IOBroker(object):
    def __init__(self,
                 addr=0x01000000,
                 broadcast=0xffffffff,
                 ioloop=None):
        self.pid = os.getpid()
        self._stop_event = threading.Event()
        self._reload_event = threading.Event()
        self.addr = addr
        self.broadcast = broadcast
        self.marshal = MarshalEnv()
        self.ports = AddrPool(minaddr=0xff)
        self.nonces = AddrPool(minaddr=0xfff)
        self.active_sys = {}
        self.local = {}
        self.links = {}
        self.remote = {}
        self.discover = {}
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
        self.providers = {}
        self._cid = list(range(1024))
        # secret; write non-zero byte as terminator
        self.secret = os.urandom(15)
        self.secret += b'\xff'
        self.uuid = uuid.uuid4()
        # masquerade cache expiration
        self._expire_thread = threading.Thread(target=self._expire_masq,
                                               name='Masquerade cache')
        self._expire_thread.setDaemon(True)
        self.ioloop = ioloop or IOLoop()

    def handle_connect(self, fd, event):
        (client, addr) = fd.accept()
        self.add_client(client)
        # announce address
        # .. _ioc-connect:
        rsp = mgmtmsg()
        rsp['header']['type'] = NLMSG_CONTROL
        rsp['cmd'] = IPRCMD_ACK
        rsp['attrs'] = [['IPR_ATTR_ADDR', self.addr]]
        rsp.encode()
        ne = envmsg()
        ne['dst'] = self.broadcast
        ne['header']['pid'] = os.getpid()
        ne['header']['type'] = NLMSG_TRANSPORT
        ne['header']['flags'] = NLT_CONTROL | NLT_RESPONSE
        ne['attrs'] = [['IPR_ATTR_CDATA',
                        rsp.buf.getvalue()]]
        ne.encode()
        client.send(ne.buf.getvalue())
        self.ioloop.register(client, self.route, defer=True)

    def alloc_addr(self):
        return self.ports.alloc()

    def dealloc_addr(self, addr):
        self.ports.free(addr)

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
                    self.nonces.free(i)
            self._stop_event.wait(60)
            if self._stop_event.is_set():
                return

    def route_control(self, sock, envelope):
        pid = envelope['header']['pid']
        nonce = envelope['header']['sequence_number']
        src = envelope['src']
        dst = envelope['dst']
        sport = envelope['sport']
        dport = envelope['dport']
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        cmd = self.parse_control(data)
        rsp = mgmtmsg()
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
                ne['header']['flags'] = NLT_CONTROL | NLT_RESPONSE
                ne['dst'] = src
                ne['src'] = dst
                ne['dport'] = sport
                ne['sport'] = dport
                ne['attrs'] = [['IPR_ATTR_CDATA', rsp.buf.getvalue()]]
                ne.encode()
                sock.send(ne.buf.getvalue())
                # Stop iothread -- shutdown sequence
                return self.shutdown()

            elif cmd['cmd'] == IPRCMD_RELOAD:
                # Reload io cycle
                self.ioloop.reload()
                rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_SERVE:
                url = cmd.get_attr('IPR_ATTR_HOST')
                key = cmd.get_attr('IPR_ATTR_SSL_KEY')
                cert = cmd.get_attr('IPR_ATTR_SSL_CERT')
                ca = cmd.get_attr('IPR_ATTR_SSL_CA')
                (new_sock, addr) = _get_socket(url, server=True,
                                               key=key,
                                               cert=cert,
                                               ca=ca)
                new_sock.setsockopt(socket.SOL_SOCKET,
                                    socket.SO_REUSEADDR, 1)
                new_sock.bind(addr)
                if new_sock.type == socket.SOCK_STREAM:
                    new_sock.listen(16)
                    self.ioloop.register(new_sock,
                                         self.handle_connect)
                else:
                    self.ioloop.register(new_sock,
                                         self.route,
                                         defer=True)
                self.servers.add(new_sock)
                self._rlist.add(new_sock)
                rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_SHUTDOWN:
                url = cmd.get_attr('IPR_ATTR_HOST')
                for old_sock in tuple(self.servers):
                    if _repr_sockets([old_sock], 'local') == [url]:
                        self._rlist.remove(old_sock)
                        self.servers.remove(old_sock)
                        self.ioloop.unregister(old_sock)
                        rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_DISCONNECT:
                # drop a connection, identified by an addr
                try:
                    uid = cmd.get_attr('IPR_ATTR_UUID')
                    old_sock = self.deregister_link(uid)
                    rsp['cmd'] = IPRCMD_ACK
                except Exception as e:
                    rsp['attrs'] = [['IPR_ATTR_ERROR', str(e)]]

            elif cmd['cmd'] == IPRCMD_PROVIDE:
                url = cmd.get_attr('IPR_ATTR_HOST')
                if url not in self.providers:
                    self.providers[url] = sock
                    rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_REMOVE:
                url = cmd.get_attr('IPR_ATTR_HOST')
                if self.providers.get(url, None) == sock:
                    del self.providers[url]
                    rsp['cmd'] = IPRCMD_ACK

            elif cmd['cmd'] == IPRCMD_CONNECT:
                # connect to a system
                try:
                    url = cmd.get_attr('IPR_ATTR_HOST')
                    key = cmd.get_attr('IPR_ATTR_SSL_KEY')
                    cert = cmd.get_attr('IPR_ATTR_SSL_CERT')
                    ca = cmd.get_attr('IPR_ATTR_SSL_CA')

                    target = urlparse.urlparse(url)
                    peer = self.addr
                    remote = False
                    established = False
                    uid = str(uuid.uuid4())

                    route = self.route

                    if url in self.providers:
                        new_sock = self.providers[url]
                        established = True
                        gate = lambda d, s:\
                            new_sock.send(self.gate_local(d, s))

                    elif target.scheme == 'netlink':
                        res = target.path.split("/")
                        new_sock = NetlinkSocket(int(res[1]))
                        new_sock.bind(int(res[2]))
                        gate = lambda d, s:\
                            new_sock.sendto(self.gate_untag(d, s),
                                            (0, 0))
                        route = self.route_netlink

                    elif target.scheme == 'udp':
                        (new_sock, addr) = _get_socket(url,
                                                       server=False)
                        gate = lambda d, s:\
                            new_sock.sendto(self.gate_forward(d, s),
                                            addr)
                        remote = True

                    else:
                        (new_sock, addr) = _get_socket(url,
                                                       server=False,
                                                       key=key,
                                                       cert=cert,
                                                       ca=ca)
                        new_sock.connect(addr)
                        remote = True
                        # stream sockets provide the peer announce
                        buf = io.BytesIO()
                        buf.length = buf.write(new_sock.recv(16384))
                        buf.seek(0)
                        msg = envmsg(buf)
                        msg.decode()
                        buf = io.BytesIO()
                        buf.length = buf.write(msg.get_attr('IPR_ATTR_CDATA'))
                        buf.seek(0)
                        msg = mgmtmsg(buf)
                        msg.decode()
                        peer = msg.get_attr('IPR_ATTR_ADDR')

                        gate = lambda d, s:\
                            new_sock.send(self.gate_forward(d, s))

                    port = self.alloc_addr()
                    link = self.register_link(uid=uid,
                                              port=port,
                                              sock=new_sock,
                                              established=established,
                                              remote=remote)
                    link.gate = gate
                    self.discover[target.path] = port
                    rsp['attrs'].append(['IPR_ATTR_UUID', uid])
                    rsp['attrs'].append(['IPR_ATTR_ADDR', peer])
                    try:
                        self.ioloop.register(new_sock, route,
                                             defer=True)
                    except Exception as e:
                        if e.errno != errno.EEXIST:
                            raise e
                    rsp['cmd'] = IPRCMD_ACK

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

            elif cmd['cmd'] == IPRCMD_DISCOVER:
                # .. _ioc-discover:
                url = cmd.get_attr('IPR_ATTR_HOST')
                if url in self.discover:
                    rsp['attrs'].append(['IPR_ATTR_ADDR', self.discover[url]])
                    rsp['cmd'] = IPRCMD_ACK

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
        ne['header']['flags'] = NLT_CONTROL | NLT_RESPONSE
        # ne['dst'] = src
        ne['src'] = dst
        ne['ttl'] = 16
        ne['dport'] = sport
        ne['sport'] = dport
        ne['attrs'] = [['IPR_ATTR_CDATA', rsp.buf.getvalue()]]
        ne.encode()
        sock.send(ne.buf.getvalue())

    def route_forward(self, sock, envelope):
        nonce = envelope['header']['sequence_number']

        envelope['ttl'] -= 1
        if envelope['ttl'] <= 0:
            return

        if (envelope['dst'] == 0) and (nonce in self.masquerade):
            return self.unmasq(nonce, envelope)
        else:
            flags = envelope['header']['flags']
            for (uid, link) in self.remote.items():
                # by default, send packets only via SOCK_STREAM,
                # and use SOCK_DGRAM only upon request

                # skip STREAM sockets if NLT_DGRAM is requested
                if ((link.sock.type == socket.SOCK_STREAM) and
                        (flags & NLT_DGRAM)):
                    continue

                # skip DGRAM sockets if NLT_DGRAM is not requested
                if ((link.sock.type == socket.SOCK_DGRAM) and
                        not (flags & NLT_DGRAM)):
                    continue

                # in any other case -- send packet
                self.remote[uid].gate(envelope, sock)

    def unmasq(self, nonce, envelope):
        target = self.masquerade[nonce]
        envelope['header']['sequence_number'] = \
            target.envelope['header']['sequence_number']
        envelope['header']['pid'] = \
            target.envelope['header']['pid']
        envelope.reset()
        envelope.encode()
        target.socket.send(envelope.buf.getvalue())

    def route_data(self, sock, envelope):
        nonce = envelope['header']['sequence_number']

        if envelope['dport'] in self.local:
            try:
                self.local[envelope['dport']].gate(envelope, sock)
            except:
                traceback.print_exc()

        elif nonce in self.masquerade:
            self.unmasq(nonce, envelope)

        else:
            # FIXME fix it, please, or kill with fire
            # there should be no data repack
            data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
            for cid, u32 in self.subscribe.items():
                self.filter_u32(u32, data)

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

    def route_netlink(self, sock, raw):
        data = io.BytesIO()
        data.length = data.write(raw)
        data.seek(8)
        seq = struct.unpack('I', data.read(4))[0]

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
            envelope['header']['sequence_number'] = \
                target.envelope['header']['sequence_number']
            envelope['header']['pid'] = \
                target.envelope['header']['pid']
            envelope['header']['type'] = NLMSG_TRANSPORT
            # envelope['dst'] = target.envelope['src']
            envelope['src'] = target.envelope['dst']
            envelope['ttl'] = 16
            envelope['dport'] = target.envelope['sport']
            envelope['sport'] = target.envelope['dport']
            envelope['attrs'] = [['IPR_ATTR_CDATA',
                                  data.getvalue()]]
            envelope.encode()
            # target
            target.socket.send(envelope.buf.getvalue())

    def route(self, sock, raw):
        """
        Route message
        """
        data = io.BytesIO()
        data.length = data.write(raw)

        if data.length == 0 and self.ioloop.unregister(sock):
            if sock in self.clients:
                self.remove_client(sock)
            else:
                self.deregister_link(fd=sock)
            return

        for envelope in self.marshal.parse(data):
            if envelope['dst'] != self.addr:
                # FORWARD
                # a packet for a remote system
                self.route_forward(sock, envelope)
            else:
                # INPUT
                # a packet for a local system
                if ((envelope['header']['flags'] & NLT_CONTROL) and not
                        (envelope['header']['flags'] & NLT_RESPONSE)):
                    # control packets
                    self.route_control(sock, envelope)
                else:
                    # transport packets
                    self.route_data(sock, envelope)

    def recv(self, fd, buf):
        ret = 0
        ret += buf.write(fd.recv(16384))
        return ret, {}

    def gate_local(self, envelope, sock):
        # 2. register way back
        nonce = self.nonces.alloc()
        masq = MasqRecord(sock)
        masq.add_envelope(envelope.copy())
        self.masquerade[nonce] = masq
        envelope['header']['sequence_number'] = nonce
        envelope['header']['pid'] = os.getpid()
        envelope.buf.seek(0)
        envelope.encode()
        # 3. return data
        return envelope.buf.getvalue()

    def gate_forward(self, envelope, sock):
        # 2. register way back
        nonce = self.nonces.alloc()
        masq = MasqRecord(sock)
        # copy envelope! original will be modified
        masq.add_envelope(envelope.copy())
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
        nonce = self.nonces.alloc()
        masq = MasqRecord(sock)
        masq.add_envelope(envelope.copy())
        masq.add_data(data)
        self.masquerade[nonce] = masq
        data.seek(8)
        data.write(struct.pack('II', nonce, self.pid))
        # 3. return data
        return data.getvalue()

    def parse_control(self, data):
        data.seek(0)
        cmd = mgmtmsg(data)
        cmd.decode()
        return cmd

    def register_link(self, uid, port, sock,
                      established=False, remote=False):
        if not established:
            self._rlist.add(sock)

        link = Link(uid, port, sock, established, remote)
        self.links[uid] = link
        if remote:
            self.remote[uid] = link
        else:
            self.local[port] = link
        return link

    def deregister_link(self, uid=None, fd=None):
        if fd is not None:
            for (uid, link) in self.links.items():
                if link.sock == fd:
                    break

        link = self.links[uid]

        if not link.keep:
            link.sock.close()
            self._rlist.remove(link.sock)

        del self.links[link.uid]
        if link.remote:
            del self.remote[link.uid]
        else:
            del self.local[link.port]
        return link.sock

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
        self._expire_thread.start()
        self.ioloop.start()

    def shutdown(self):
        self._stop_event.set()
        for sock in self.servers:
            sock.close()
        # shutdown sequence
        self.ioloop.shutdown()
        self.ioloop.join()
        self._expire_thread.join()
