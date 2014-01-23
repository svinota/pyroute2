import urlparse
import threading
import struct
import os
import io

from pyroute2.common import uuid32
from pyroute2.netlink import NLMSG_CONTROL
from pyroute2.netlink import NLMSG_TRANSPORT
from pyroute2.netlink import IPRCMD_ACK
from pyroute2.netlink import IPRCMD_SERVE
from pyroute2.netlink import IPRCMD_REGISTER
from pyroute2.netlink import IPRCMD_SHUTDOWN
from pyroute2.netlink import IPRCMD_CONNECT
from pyroute2.netlink import IPRCMD_DISCONNECT
from pyroute2.netlink import IPRCMD_UNSUBSCRIBE
from pyroute2.netlink import IPRCMD_SUBSCRIBE
from pyroute2.netlink import IPRCMD_PROVIDE
from pyroute2.netlink import IPRCMD_REMOVE
from pyroute2.netlink import IPRCMD_DISCOVER
from pyroute2.netlink import NLMSG_DONE
from pyroute2.netlink import NLM_F_MULTI
from pyroute2.netlink.generic import mgmtmsg
from pyroute2.netlink.generic import envmsg
from pyroute2.iocore import NLT_CONTROL
from pyroute2.iocore import NLT_RESPONSE
from pyroute2.iocore import NLT_EXCEPTION
from pyroute2.iocore.loop import IOLoop
from pyroute2.iocore.broker import pairPipeSockets
from pyroute2.iocore.broker import IOBroker

try:
    import Queue
except ImportError:
    import queue as Queue
_QUEUE_MAXSIZE = 4096


class IOCore(object):

    marshal = None
    name = 'Core API'
    default_target = None

    def __init__(self, debug=False, timeout=3, do_connect=False,
                 host=None, key=None, cert=None, ca=None,
                 addr=None):
        addr = addr or uuid32()
        self._timeout = timeout
        self.default_broker = addr
        self.default_dport = 0
        self.uids = set()
        self.listeners = {}     # {nonce: Queue(), ...}
        self.callbacks = []     # [(predicate, callback, args), ...]
        self.debug = debug
        self.cid = None
        self._nonce = 0
        self.save = None
        self._nonce_lock = threading.Lock()
        if self.marshal is not None:
            self.marshal.debug = debug
            self.marshal = self.marshal()
        self.buffers = Queue.Queue()
        self._mirror = False
        self.host = host

        self.ioloop = IOLoop()

        self.iobroker = IOBroker(addr=addr, ioloop=self.ioloop)
        self.iobroker.start()
        self._brs, self.bridge = pairPipeSockets()
        self.iobroker.add_client(self._brs)
        self.iobroker.controls.add(self._brs)
        self.ioloop.register(self._brs,
                             self.iobroker.route,
                             defer=True)
        self.ioloop.register(self.bridge,
                             self._route,
                             defer=True)
        if do_connect:
            path = urlparse.urlparse(host).path
            (self.default_link,
             self.default_peer) = self.connect(self.host,
                                               key, cert, ca)
            self.default_dport = self.discover(self.default_target or path,
                                               self.default_peer)

    def _route(self, sock, raw):
        buf = io.BytesIO()
        buf.length = buf.write(raw)
        buf.seek(0)

        if self.save is not None:
            # concatenate buffers
            buf.seek(0)
            self.save.write(buf.read())
            self.save.length += buf.length
            # discard save
            buf = self.save
            self.save = None

        offset = 0
        while offset < buf.length:
            buf.seek(offset)
            (length,
             mtype,
             flags) = struct.unpack('IHH', buf.read(8))

            if offset + length > buf.length:
                # create save buffer
                buf.seek(offset)
                self.save = io.BytesIO()
                self.save.length = self.save.write(buf.read())
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
                if ((flags & NLT_CONTROL) and
                        (flags & NLT_RESPONSE)):
                    msg = mgmtmsg(buf)
                    msg.decode()
                    self.listeners[nonce].put_nowait(msg)
                else:
                    self.parse(envelope, buf)
            except AttributeError:
                # now silently drop bad packet
                pass

            offset += length

    def parse(self, envelope, data):

        if self.marshal is None:
            nonce = envelope['header']['sequence_number']
            if envelope['header']['flags'] & NLT_EXCEPTION:
                msgs = [{'header': {'sequence_number': nonce},
                         'error': RuntimeError(data.getvalue()),
                         'data': None}]
            else:
                msgs = [{'header': {'sequence_number': nonce},
                         'error': None,
                         'data': data.getvalue()}]
        else:
            msgs = self.marshal.parse(data)

        for msg in msgs:
            try:
                key = msg['header']['sequence_number']
            except (TypeError, KeyError):
                key = 0

            # 8<--------------------------------------------------------------
            # message filtering
            # right now it is simply iterating callback list
            # .. _ioc-callbacks:
            skip = False

            for cr in self.callbacks:
                if cr[0](envelope, msg):
                    if cr[1](envelope, msg, *cr[2]) is not None:
                        skip = True

            if skip:
                continue

            # 8<--------------------------------------------------------------
            if key not in self.listeners:
                key = 0

            if self._mirror and (key != 0) and (msg.raw is not None):
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

    def command(self, cmd, attrs=[], expect=None, addr=None):
        addr = addr or self.default_broker
        msg = mgmtmsg(io.BytesIO())
        msg['cmd'] = cmd
        msg['attrs'] = attrs
        msg['header']['type'] = NLMSG_CONTROL
        msg.encode()
        rsp = self.request(msg.buf.getvalue(),
                           env_flags=NLT_CONTROL,
                           addr=addr)[0]
        assert rsp['cmd'] == IPRCMD_ACK
        if expect is not None:
            if type(expect) not in (list, tuple):
                return rsp.get_attr(expect)
            else:
                ret = []
                for item in expect:
                    ret.append(rsp.get_attr(item))
                return ret
        else:
            return None

    def register(self, secret, addr=None):
        return self.command(IPRCMD_REGISTER,
                            [['IPR_ATTR_SECRET', secret]],
                            addr=addr)

    def discover(self, url, addr=None):
        # .. _ioc-discover:
        return self.command(IPRCMD_DISCOVER,
                            [['IPR_ATTR_HOST', url]],
                            expect='IPR_ATTR_ADDR',
                            addr=addr)

    def provide(self, url):
        self.command(IPRCMD_PROVIDE, [['IPR_ATTR_HOST', url]])
        return self.command(IPRCMD_CONNECT, [['IPR_ATTR_HOST', url]])

    def remove(self, url):
        return self.command(IPRCMD_REMOVE, [['IPR_ATTR_HOST', url]])

    def serve(self, url, key='', cert='', ca='', addr=None):
        return self.command(IPRCMD_SERVE,
                            [['IPR_ATTR_HOST', url],
                             ['IPR_ATTR_SSL_KEY', key],
                             ['IPR_ATTR_SSL_CERT', cert],
                             ['IPR_ATTR_SSL_CA', ca]],
                            addr=addr)

    def shutdown(self, url, addr=None):
        return self.command(IPRCMD_SHUTDOWN,
                            [['IPR_ATTR_HOST', url]],
                            addr=addr)

    def connect(self, host=None, key='', cert='', ca='', addr=None):
        host = host or self.host
        (uid,
         peer) = self.command(IPRCMD_CONNECT,
                              [['IPR_ATTR_HOST', host],
                               ['IPR_ATTR_SSL_KEY', key],
                               ['IPR_ATTR_SSL_CERT', cert],
                               ['IPR_ATTR_SSL_CA', ca]],
                              expect=['IPR_ATTR_UUID',
                                      'IPR_ATTR_ADDR'],
                              addr=addr)
        self.uids.add((uid, addr))
        return uid, peer

    def disconnect(self, uid, addr=None):
        ret = self.command(IPRCMD_DISCONNECT,
                           [['IPR_ATTR_UUID', uid]],
                           addr=addr)
        self.uids.remove((uid, addr))
        return ret

    def release(self):
        '''
        Shutdown all threads and release netlink sockets
        '''
        for (uid, addr) in tuple(self.uids):
            try:
                self.disconnect(uid, addr=addr)
            except Queue.Empty as e:
                if addr == self.default_broker:
                    raise e
        self.iobroker.shutdown()

        self._brs.send(struct.pack('I', 4))
        self._brs.close()
        self.bridge.close()

    def mirror(self, operate=True):
        '''
        Turn message mirroring on/off. When it is 'on', all
        received messages will be copied (mirrored) into the
        default 0 queue.
        '''
        self.monitor(operate)
        self._mirror = operate

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
        if operate and self.cid is None:
            self.listeners[0] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
            self.cid = self.command(IPRCMD_SUBSCRIBE,
                                    [['IPR_ATTR_KEY', {'offset': 8,
                                                       'key': 0,
                                                       'mask': 0}]],
                                    expect='IPR_ATTR_CID')
        else:
            self.command(IPRCMD_UNSUBSCRIBE,
                         [['IPR_ATTR_CID', self.cid]])
            self.cid = None
            del self.listeners[0]

    def register_callback(self, callback,
                          predicate=lambda e, x: True, args=None):
        '''
        Register a callback to run on a message arrival.

        Callback is the function that will be called with the
        message as the first argument. Predicate is the optional
        callable object, that returns True or False. Upon True,
        the callback will be called. Upon False it will not.
        Args is a list or tuple of arguments.

        Simplest example, assume ipr is the IPRoute() instance::

            # create a simplest callback that will print messages
            def cb(env, msg):
                print(msg)

            # register callback for any message:
            ipr.register_callback(cb)

        More complex example, with filtering::

            # Set object's attribute after the message key
            def cb(env, msg, obj):
                obj.some_attr = msg["some key"]

            # Register the callback only for the loopback device, index 1:
            ipr.register_callback(cb,
                                  lambda e, x: x.get('index', None) == 1,
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
            if self.marshal is None:
                if msg.get('error', None) is not None:
                    raise msg['error']
                else:
                    return [msg.get('data', msg)]
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

    def nonce(self):
        with self._nonce_lock:
            if self._nonce == 0xffffffff:
                self._nonce = 1
            else:
                self._nonce += 1
            return self._nonce

    def push(self, host, msg,
             env_flags=None,
             nonce=0,
             cname=None):
        addr, port = host
        envelope = envmsg()
        envelope['header']['sequence_number'] = nonce
        envelope['header']['pid'] = os.getpid()
        envelope['header']['type'] = NLMSG_TRANSPORT
        if env_flags is not None:
            envelope['header']['flags'] = env_flags
        envelope['dst'] = addr
        envelope['src'] = self.default_broker
        envelope['dport'] = port
        envelope['ttl'] = 16
        envelope['attrs'] = [['IPR_ATTR_CDATA', msg]]
        if cname is not None:
            envelope['attrs'].append(['IPR_ATTR_CNAME', cname])
        envelope.encode()
        self.bridge.send(envelope.buf.getvalue())

    def request(self, msg,
                env_flags=0,
                addr=None,
                port=None,
                nonce=None,
                cname=None,
                response_timeout=None):
        nonce = nonce or self.nonce()
        port = port or self.default_dport
        addr = addr or self.default_broker
        self.listeners[nonce] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self.push((addr, port), msg, env_flags, nonce, cname)
        return self.get(nonce, timeout=response_timeout)
