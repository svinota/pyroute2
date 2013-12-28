import threading
import select
import struct
import os
import io

from pyroute2.netlink import NLMSG_CONTROL
from pyroute2.netlink import NLMSG_TRANSPORT
from pyroute2.netlink import IPRCMD_ACK
from pyroute2.netlink import IPRCMD_SERVE
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
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink.generic import mgmtmsg
from pyroute2.netlink.generic import envmsg
from pyroute2.iocore.broker import pairPipeSockets
from pyroute2.iocore.broker import IOBroker

try:
    import Queue
except ImportError:
    import queue as Queue
_QUEUE_MAXSIZE = 4096


class IOCore(threading.Thread):

    family = 0
    groups = 0
    marshal = None
    do_connect = False
    name = 'Core API'

    def __init__(self, debug=False, timeout=3000, do_connect=None,
                 host=None, key=None, cert=None, ca=None,
                 addr=0x01000000):
        threading.Thread.__init__(self, name=self.name)
        self._timeout = timeout
        self.iothread = IOBroker(addr=addr)
        self.default_broker = addr
        self.default_dport = 0
        self.uids = set()
        self.listeners = {}     # {nonce: Queue(), ...}
        self.callbacks = []     # [(predicate, callback, args), ...]
        self.debug = debug
        self.cid = None
        self._nonce = 0
        self._nonce_lock = threading.Lock()
        if self.marshal is not None:
            self.marshal.debug = debug
            self.marshal = self.marshal()
        self.buffers = Queue.Queue()
        self._mirror = False
        default_target = 'netlink://%i:%i' % (self.family, self.groups)
        self.host = host or default_target
        self._run_event = threading.Event()
        self._stop_event = threading.Event()
        self._feed_thread = threading.Thread(target=self._feed_buffers,
                                             name='Reasm and parsing')
        self._feed_thread.setDaemon(True)
        self._feed_thread.start()
        self.setDaemon(True)
        self.start()
        self._run_event.wait()
        if do_connect is not None:
            self.do_connect = do_connect
        if self.do_connect:
            (self.default_link,
             self.default_peer) = self.connect(self.host, key, cert, ca)
            self.default_dport = self.discover(default_target,
                                               self.default_peer)

    def run(self):
        # 1. run iothread
        self.iothread.start()
        # 2. connect to iothread
        self._brs, self.bridge = pairPipeSockets()
        self.iothread.add_client(self._brs)
        self.iothread.controls.add(self._brs)
        self.iothread.reload()
        self._run_event.set()

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
                    if flags == 3:
                        msg = mgmtmsg(buf)
                        msg.decode()
                        self.listeners[nonce].put_nowait(msg)
                    elif self.marshal is None:
                        msg = envelope.get_attr('IPR_ATTR_CDATA')
                        self.listeners[0].put_nowait(msg)
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
        rsp = self.nlm_request(msg, NLMSG_CONTROL, 0, 1, addr)[0]
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

    def discover(self, url, addr=None):
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
        self.uids.add(uid)
        return uid, peer

    def disconnect(self, uid, addr=None):
        ret = self.command(IPRCMD_DISCONNECT,
                           [['IPR_ATTR_UUID', uid]],
                           addr=addr)
        self.uids.remove(uid)
        return ret

    def release(self):
        '''
        Shutdown all threads and release netlink sockets
        '''
        for uid in tuple(self.uids):
            self.disconnect(uid)
        self.iothread.stop()

        self._stop_event.set()
        self._brs.send(struct.pack('I', 4))
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
            if self.marshal is None:
                return [msg]
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

    def push(self, addr, port, msg,
             env_flags=None,
             nonce=0):
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
        envelope.encode()
        self.bridge.send(envelope.buf.getvalue())

    def request(self, msg,
                env_flags=0,
                addr=None,
                port=None,
                response_timeout=None):
        port = port or self.default_dport
        addr = addr or self.default_broker
        self.nlm_push(msg, env_flags, addr, port)
        return self.get(0, timeout=response_timeout)

    def nlm_push(self, msg,
                 msg_type=None,
                 msg_flags=None,
                 env_flags=None,
                 addr=0,
                 port=0,
                 nonce=0):
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        if msg_type is not None:
            msg['header']['type'] = msg_type
        if msg_flags is not None:
            msg['header']['flags'] = msg_flags
        msg.encode()
        self.push(addr, port, msg.buf.getvalue(), env_flags, nonce)

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST,
                    env_flags=0,
                    addr=None,
                    port=None,
                    response_timeout=None):
        '''
        Send netlink request, filling common message
        fields, and wait for response.
        '''
        port = port or self.default_dport
        addr = addr or self.default_peer
        nonce = self.nonce()
        self.listeners[nonce] = Queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self.nlm_push(msg, msg_type, msg_flags, env_flags, addr, port, nonce)
        result = self.get(nonce, timeout=response_timeout)
        for msg in result:
            # reset message buffer, make it ready for encoding back
            msg.reset()
            if not self.debug:
                del msg['header']
        return result
