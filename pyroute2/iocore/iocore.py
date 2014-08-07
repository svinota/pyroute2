import struct
import copy
import uuid
import os
import io

from multiprocessing import Process
from pyroute2.common import uuid32
from pyroute2.common import debug
from pyroute2.iocore import TimeoutError
from pyroute2.netlink import NLMSG_CONTROL
from pyroute2.netlink import NLMSG_TRANSPORT
from pyroute2.netlink import IPRCMD_ACK
from pyroute2.netlink import IPRCMD_SERVE
from pyroute2.netlink import IPRCMD_REGISTER
from pyroute2.netlink import IPRCMD_UNREGISTER
from pyroute2.netlink import IPRCMD_SHUTDOWN
from pyroute2.netlink import IPRCMD_CONNECT
from pyroute2.netlink import IPRCMD_DISCONNECT
from pyroute2.netlink import IPRCMD_UNSUBSCRIBE
from pyroute2.netlink import IPRCMD_SUBSCRIBE
from pyroute2.netlink import IPRCMD_PROVIDE
from pyroute2.netlink import IPRCMD_REMOVE
from pyroute2.netlink import IPRCMD_DISCOVER
from pyroute2.netlink import IPRCMD_STOP
from pyroute2.netlink import NLMSG_DONE
from pyroute2.netlink import NLM_F_MULTI
from pyroute2.netlink.generic import mgmtmsg
from pyroute2.netlink.generic import envmsg
from pyroute2.iocore import NLT_CONTROL
from pyroute2.iocore import NLT_RESPONSE
from pyroute2.iocore import NLT_EXCEPTION
from pyroute2.iocore.loop import IOLoop
from pyroute2.iocore.broker import pairPipeSockets
from pyroute2.iocore.broker import MarshalEnv
from pyroute2.iocore.broker import IOBroker
from pyroute2.iocore.addrpool import AddrPool

try:
    import Queue
except ImportError:
    import queue as Queue
_QUEUE_MAXSIZE = 4096

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class IOCore(object):

    marshal = None
    name = 'Core API'
    default_target = None

    def __init__(self, debug=False, timeout=3, do_connect=False,
                 host=None, key=None, cert=None, ca=None,
                 addr=None, fork=False, secret=None):
        addr = addr or uuid32()
        self._timeout = timeout
        self.default_broker = addr
        self.default_dport = 0
        self.uids = set()
        self.listeners = {}     # {nonce: Queue(), ...}
        self.callbacks = []     # [(predicate, callback, args), ...]
        self.debug = debug
        self.cid = None
        self.cmd_nonce = AddrPool(minaddr=0xf, maxaddr=0xfffe)
        self.nonce = AddrPool(minaddr=0xffff, maxaddr=0xffffffff)
        self.emarshal = MarshalEnv()
        self.save = None
        if self.marshal is not None:
            self.marshal.debug = debug
            self.marshal = self.marshal()
        self.buffers = Queue.Queue()
        self._mirror = False
        self.host = host

        self.ioloop = IOLoop()

        self._brs, self.bridge = pairPipeSockets()
        # To fork or not to fork?
        #
        # It depends on how you gonna use RT netlink sockets
        # in your application. Performance can also differ,
        # and sometimes forked broker can even speedup your
        # application -- keep in mind Python's GIL
        if fork:
            # Start the I/O broker in a separate process,
            # so you can use multiple RT netlink sockets in
            # one application -- it does matter, if your
            # application already uses some RT netlink
            # library and you want to smoothly try and
            # migrate to the pyroute2
            self.forked_broker = Process(target=self._start_broker,
                                         args=(fork, secret))
            self.forked_broker.start()
        else:
            # Start I/O broker as an embedded object, so
            # the RT netlink socket will be opened in the
            # same process. Technically, you can open
            # multiple RT netlink sockets within one process,
            # but only the first one will receive all the
            # answers -- so effectively only one socket per
            # process can be used.
            self.forked_broker = None
            self._start_broker(fork, secret)
        self.ioloop.start()
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

    def _start_broker(self, fork=False, secret=None):
        iobroker = IOBroker(addr=self.default_broker,
                            ioloop=None if fork else self.ioloop,
                            control=self._brs, secret=secret)
        iobroker.start()
        if fork:
            iobroker._stop_event.wait()

    @debug
    def _route(self, sock, raw):
        data = io.BytesIO()
        data.length = data.write(raw)

        for envelope in self.emarshal.parse(data, sock):

            nonce = envelope['header']['sequence_number']
            flags = envelope['header']['flags']
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

    @debug
    def parse(self, envelope, data):

        if self.marshal is None:
            nonce = envelope['header']['sequence_number']
            if envelope['header']['flags'] & NLT_EXCEPTION:
                error = RuntimeError(data.getvalue())
                msgs = [{'header': {'sequence_number': nonce,
                                    'type': 0,
                                    'flags': 0,
                                    'error': error},
                         'data': None}]
            else:
                msgs = [{'header': {'sequence_number': nonce,
                                    'type': 0,
                                    'flags': 0,
                                    'error': None},
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

            if self._mirror and (key != 0):
                # On Python 2.6 it can fail due to class fabrics
                # in nlmsg definitions, so parse it again. It should
                # not be much slower than copy.deepcopy()
                if getattr(msg, 'raw', None) is not None:
                    raw = io.BytesIO()
                    raw.length = raw.write(msg.raw)
                    new = self.marshal.parse(raw)[0]
                else:
                    new = copy.deepcopy(msg)
                self.listeners[0].put_nowait(new)

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

        # try to send a command 3 times
        for _ in range(3):
            try:
                rsp = self.request(msg.buf.getvalue(),
                                   env_flags=NLT_CONTROL,
                                   nonce_pool=self.cmd_nonce,
                                   addr=addr)[0]
            except Queue.Empty:
                # if there is no reply, try again
                # rsp variable will be initialized
                continue

            # if there is a reply, continue execution
            # (break the loop)
            break

        else:
            # if there was no break -- raise Queue.Empty()
            # for compatibility
            raise Queue.Empty()

        if rsp['cmd'] != IPRCMD_ACK:
            raise RuntimeError(rsp.get_attr('IPR_ATTR_ERROR'))
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

    def unregister(self, addr=None):
        return self.command(IPRCMD_UNREGISTER, addr=addr)

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
            except TimeoutError as e:
                if addr == self.default_broker:
                    raise e
        self.command(IPRCMD_STOP)
        if self.forked_broker:
            self.forked_broker.join()
        self.ioloop.shutdown()
        self._brs.send(struct.pack('I', 4))
        self._brs.close()
        self.bridge.close()

    def mirror(self, operate=True):
        '''
        Turn message mirroring on/off. When it is 'on', all
        received messages will be copied (mirrored) into the
        default 0 queue.
        '''
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

    @debug
    def get(self, key=0, raw=False, timeout=None, terminate=None,
            nonce_pool=None):
        '''
        Get a message from a queue

        * key -- message queue number
        '''
        nonce_pool = nonce_pool or self.nonce
        queue = self.listeners[key]
        result = []
        e = None
        timeout = (timeout or self._timeout) if (key != 0) else 0xffff
        while True:
            # timeout should also be set to catch ctrl-c
            # Bug-Url: http://bugs.python.org/issue1360
            try:
                msg = queue.get(block=True, timeout=timeout)
            except Queue.Empty:
                e = TimeoutError()
                if key == 0:
                    continue
                else:
                    break

            if (terminate is not None) and terminate(msg):
                break

            # exceptions
            if msg['header'].get('error', None) is not None:
                e = msg['header']['error']

            # RPC
            if self.marshal is None:
                data = msg.get('data', msg)
            else:
                data = msg

            # Netlink
            if (msg['header']['type'] != NLMSG_DONE):
                result.append(data)

            # break the loop if any
            if (key == 0) or (e is not None):
                break

            # wait for NLMSG_DONE if NLM_F_MULTI
            if (terminate is None) and (
                    (msg['header']['type'] == NLMSG_DONE) or
                    (not msg['header']['flags'] & NLM_F_MULTI)):
                break

        if key != 0:
            # delete the queue
            del self.listeners[key]
            nonce_pool.free(key)
            # get remaining messages from the queue and
            # re-route them to queue 0 or drop
            while not queue.empty():
                msg = queue.get()
                if 0 in self.listeners:
                    self.listeners[0].put(msg)

        if e is not None:
            raise e

        return result

    @debug
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
        envelope['id'] = uuid.uuid4().bytes
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
                nonce_pool=None,
                cname=None,
                response_timeout=None,
                terminate=None):
        nonce_pool = nonce_pool or self.nonce
        nonce = nonce or nonce_pool.alloc()
        port = port or self.default_dport
        addr = addr or self.default_broker
        self.listeners[nonce] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self.push((addr, port), msg, env_flags, nonce, cname)
        return self.get(nonce,
                        nonce_pool=nonce_pool,
                        timeout=response_timeout,
                        terminate=terminate)
