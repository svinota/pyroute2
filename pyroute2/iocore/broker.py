import traceback
import threading
import socket
import struct
import time
import os
import io
import uuid
import ssl

from pyroute2.common import AF_PIPE
from pyroute2.netlink import Marshal
from pyroute2.netlink import NLMSG_CONTROL
from pyroute2.netlink import NLMSG_TRANSPORT
from pyroute2.netlink import IPRCMD_ERR
from pyroute2.netlink import IPRCMD_ACK
from pyroute2.netlink.generic import mgmtmsg
from pyroute2.netlink.generic import envmsg
from pyroute2.iocore import NLT_CONTROL
from pyroute2.iocore import NLT_RESPONSE
from pyroute2.iocore import NLT_DGRAM
from pyroute2.iocore.modules import modules
from pyroute2.iocore.loop import IOLoop
from pyroute2.iocore.addrpool import AddrPool
from pyroute2.iocore.utils import access

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


class Cache(threading.Thread):

    def __init__(self, stop_event):
        threading.Thread.__init__(self)
        self.stop_event = stop_event
        self.maps = []
        self.cb = {}

    def register_map(self, m, cb=None):
        self.maps.append(m)
        if cb:
            self.cb[id(m)] = cb

    def unregister_map(self, m):
        self.maps.remove(m)

    def run(self):
        while True:
            # expire masquerade records
            ts = time.time()
            for m in self.maps:
                for k in tuple(m.keys()):
                    if (ts - m[k].ctime) > 60:
                        del m[k]
                        if self.cb.get(id(m)):
                            self.cb[id(m)](k)
            self.stop_event.wait(60)
            if self.stop_event.is_set():
                return


class CacheRecord(object):

    def __init__(self, data):
        self.data = data
        self.ctime = time.time()

    def __eq__(self, mit):
        return self.data == mit


class MasqRecord(CacheRecord):

    def __init__(self, socket):
        CacheRecord.__init__(self, None)
        self.envelope = None
        self.socket = socket

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
                 ioloop=None,
                 control=None,
                 secret=None):
        self.pid = os.getpid()
        self._stop_event = threading.Event()
        self._reload_event = threading.Event()
        self.shutdown_flag = threading.Event()
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
        self.packet_ids = {}      # {int: CacheRecord()...}
        self.clients = set()      # set(socket, socket...)
        self.servers = set()      # set(socket, socket...)
        self.controls = set()     # set(socket, socket...)
        self.sockets = {}
        self.subscribe = {}
        self.providers = {}
        # modules = { IPRCMD_STOP: {'access': access.ADMIN,
        #                           'command': <function>},
        #             IPRCMD_...: ...
        self.modules = dict(((x.target, {'access': x.level,
                                         'command': x.command})
                             for x in modules))
        self._cid = list(range(1024))
        # secret; write non-zero byte as terminator
        if secret:
            self.secret = secret
        else:
            self.secret = os.urandom(15)
            self.secret += b'\xff'
        self.uuid = uuid.uuid4()
        # masquerade cache expiration
        self._expire_thread = Cache(self._stop_event)
        self._expire_thread.register_map(self.masquerade, self.nonces.free)
        self._expire_thread.register_map(self.packet_ids)
        self._expire_thread.setDaemon(True)
        if ioloop:
            self.ioloop = ioloop
            self.standalone = False
        else:
            self.ioloop = IOLoop()
            self.standalone = True
        if control:
            self.add_client(control)
            self.controls.add(control)
            self.ioloop.register(control, self.route, defer=True)

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
        ne['id'] = uuid.uuid4().bytes
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

    def route_control(self, sock, envelope):
        pid = envelope['header']['pid']
        nonce = envelope['header']['sequence_number']
        # src = envelope['src']
        dst = envelope['dst']
        sport = envelope['sport']
        dport = envelope['dport']
        data = io.BytesIO(envelope.get_attr('IPR_ATTR_CDATA'))
        cmd = self.parse_control(data)
        module = cmd['cmd']
        rsp = mgmtmsg()
        rsp['header']['type'] = NLMSG_CONTROL
        rsp['header']['sequence_number'] = nonce
        rsp['cmd'] = IPRCMD_ERR
        rsp['attrs'] = []

        rights = 0
        if sock in self.controls:
            rights = access.ADMIN
        elif sock in self.clients:
            rights = access.USER
        try:
            if rights & self.modules[module]['access']:
                self.modules[module]['command'](self, sock, envelope,
                                                cmd, rsp)
            else:
                raise IOError(13, 'Permission denied')

            rsp['cmd'] = IPRCMD_ACK
            rsp['attrs'].append(['IPR_ATTR_SOURCE', cmd['cmd']])
        except Exception:
            rsp['attrs'] = [['IPR_ATTR_ERROR', traceback.format_exc()]]

        rsp.encode()
        ne = envmsg()
        ne['header']['sequence_number'] = nonce
        ne['header']['pid'] = pid
        ne['header']['type'] = NLMSG_TRANSPORT
        ne['header']['flags'] = NLT_CONTROL | NLT_RESPONSE
        ne['src'] = dst
        ne['ttl'] = 16
        ne['id'] = uuid.uuid4().bytes
        ne['dport'] = sport
        ne['sport'] = dport
        ne['attrs'] = [['IPR_ATTR_CDATA', rsp.buf.getvalue()]]
        ne.encode()
        sock.send(ne.buf.getvalue())

        if self.shutdown_flag.is_set():
            self.shutdown()

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
        envelope['id'] = uuid.uuid4().bytes
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
            envelope['id'] = uuid.uuid4().bytes
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

        for envelope in self.marshal.parse(data, sock):
            if envelope['id'] in self.packet_ids:
                # drop duplicated packets
                continue
            else:
                # register packet id
                self.packet_ids[envelope['id']] = CacheRecord(None)

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
        sock.close()
        return sock

    def start(self):
        self._expire_thread.start()
        if self.standalone:
            self.ioloop.start()

    def shutdown(self):
        self._stop_event.set()
        for sock in self.servers:
            sock.close()
        # shutdown sequence
        self._expire_thread.join()
        if self.standalone:
            self.ioloop.shutdown()
