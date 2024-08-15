import asyncio
import collections
import errno
import logging
import multiprocessing
import os
import socket
from urllib import parse

from pyroute2 import config
from pyroute2.common import AddrPool
from pyroute2.netlink import NLM_F_MULTI, NLMSG_DONE
from pyroute2.netns import setns
from pyroute2.requests.main import RequestProcessor

log = logging.getLogger(__name__)
Stats = collections.namedtuple('Stats', ('qsize', 'delta', 'delay'))


class CoreSocketSpec(dict):
    def __init__(self, spec=None):
        super().__init__(spec)
        spec = {} if spec is None else spec
        default = {'closed': False, 'compiled': None, 'uname': config.uname}
        self.status = RequestProcessor()
        self.status.update(default)
        self.status.update(self)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.status.update(self)

    def __delitem__(self, key):
        super().__delitem__(key)
        self.status.update(self)


class CoreMessageQueue:

    def __init__(self):
        self.queues = {0: asyncio.Queue()}
        self.root = self.queues[0]

    async def join(self):
        return await self.root.join()

    async def reschedule(self, target):
        while not self.root.empty():
            target.append(await self.root.get())
            self.root.task_done()
        for key in tuple(self.queues.keys()):
            del self.queues[key]

    async def get(self, tag):
        ret = await self.queues[tag].get()
        self.queues[tag].task_done()
        return ret

    async def put(self, tag, message):
        if tag not in self.queues:
            tag = 0
        return await self.queues[tag].put(message)

    def ensure(self, tag):
        if tag not in self.queues:
            self.queues[tag] = asyncio.Queue()

    def put_nowait(self, tag, message):
        if tag not in self.queues:
            tag = 0
        return self.queues[tag].put_nowait(message)


class CoreProtocol(asyncio.Protocol):
    def __init__(self, on_con_lost, enqueue):
        self.transport = None
        self.enqueue = enqueue
        self.on_con_lost = on_con_lost

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)


class CoreStreamProtocol(CoreProtocol):

    def data_received(self, data):
        log.debug('SOCK_STREAM enqueue %s bytes' % len(data))
        self.enqueue(data, None)


class CoreDatagramProtocol(CoreProtocol):

    def datagram_received(self, data, addr):
        log.debug('SOCK_DGRAM enqueue %s bytes' % len(data))
        self.enqueue(data, addr)


def netns_init(ctl, nsname, cls):
    setns(nsname)
    s = cls()
    print(" <<< ", s)
    socket.send_fds(ctl, [b'test'], [s.socket.fileno()], 1)
    print(" done ")


class CoreSocket:
    '''Pyroute2 core socket class.

    This class implements the core socket concept for all the pyroute2
    communications, both Netlink and internal RPC.
    '''

    libc = None
    socket = None
    compiled = None
    endpoint = None
    event_loop = None
    __spec = None
    __marshal = None

    def __init__(
        self,
        target='localhost',
        rcvsize=16384,
        use_socket=None,
        netns=None,
        flags=os.O_CREAT,
        libc=None,
        groups=0,
    ):
        # 8<-----------------------------------------
        self.spec = CoreSocketSpec(
            {
                'target': target,
                'use_socket': use_socket is not None,
                'rcvsize': rcvsize,
                'netns': netns,
                'flags': flags,
                'groups': groups,
            }
        )
        if libc is not None:
            self.libc = libc
        self.status = self.spec.status
        url = parse.urlparse(self.status['target'])
        self.scheme = url.scheme if url.scheme else url.path
        self.use_socket = use_socket
        # 8<-----------------------------------------
        # Setup netns
        if self.spec['netns'] is not None:
            # inspect self.__init__ argument names
            ctrl = socket.socketpair()
            nsproc = multiprocessing.Process(
                target=netns_init,
                args=(ctrl[0], self.spec['netns'], type(self)),
            )
            nsproc.start()
            (_, (self.spec['fileno'],), _, _) = socket.recv_fds(
                ctrl[1], 1024, 1
            )
            nsproc.join()
        # 8<-----------------------------------------
        self.callbacks = []  # [(predicate, callback, args), ...]
        self.addr_pool = AddrPool(minaddr=0x000000FF, maxaddr=0x0000FFFF)
        self.marshal = None
        self.buffer = []
        self.msg_reschedule = []
        # 8<-----------------------------------------
        # Setup the underlying socket
        self.socket = self.setup_socket()
        self.msg_queue = CoreMessageQueue()
        self.event_loop = self.setup_event_loop()
        self.connection_lost = self.event_loop.create_future()
        if self.event_loop.is_running():
            self.endpoint_started = asyncio.ensure_future(
                self.setup_endpoint()
            )
        else:
            self.event_loop.run_until_complete(self.setup_endpoint())
            self.endpoint_started = self.event_loop.create_future()
            self.endpoint_started.set_result(True)

    def get_loop(self):
        return self.event_loop

    @property
    def spec(self):
        return self.__spec

    @spec.setter
    def spec(self, value):
        if self.__spec is None:
            self.__spec = value

    @property
    def marshal(self):
        return self.__marshal

    @marshal.setter
    def marshal(self, value):
        if self.__marshal is None:
            self.__marshal = value

    async def setup_endpoint(self, loop=None):
        # Setup asyncio
        if self.endpoint is not None:
            return
        self.endpoint = await self.event_loop.connect_accepted_socket(
            lambda: CoreStreamProtocol(self.connection_lost, self.enqueue),
            sock=self.socket,
        )

    def setup_event_loop(self, event_loop=None):
        if event_loop is None:
            try:
                event_loop = asyncio.get_running_loop()
                self.status['event_loop'] = 'auto'
            except RuntimeError:
                event_loop = asyncio.new_event_loop()
                self.status['event_loop'] = 'new'
        return event_loop

    def setup_socket(self, sock=None):
        if self.status['use_socket']:
            return self.use_socket
        sock = self.socket if sock is None else sock
        if sock is not None:
            sock.close()
        sock = config.SocketBase(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def __getattr__(self, attr):
        if attr in (
            'getsockname',
            'getsockopt',
            'makefile',
            'setsockopt',
            'setblocking',
            'settimeout',
            'gettimeout',
            'shutdown',
            'recvfrom',
            'recvfrom_into',
            'fileno',
            'sendto',
            'connect',
            'listen',
        ):
            return getattr(self.socket, attr)
        elif attr in ('_sendto', '_recv', '_recv_into'):
            return getattr(self.socket, attr.lstrip("_"))
        raise AttributeError(attr)

    def bind(self, addr):
        '''Bind the socket to the address.'''
        return self.socket.bind(addr)

    def close(self, code=errno.ECONNRESET):
        '''Correctly close the socket and free all the resources.'''
        self.socket.close()

    def clone(self):
        '''Return a copy of itself with a new underlying socket.'''
        new_spec = {}
        for key, value in self.spec.items():
            if key in self.__init__.__code__.co_varnames:
                new_spec[key] = value
        return type(self)(**new_spec)

    def recv(self, buffersize, flags=0):
        '''Get one buffer from the socket.'''
        return self.socket.recv(buffersize, flags)

    def send(self, data, flags=0):
        '''Send one buffer via the socket.'''
        return self.socket.send(data, flags)

    def accept(self):
        if self.status['use_socket']:
            return (self, None)
        (connection, address) = self.socket.accept()
        new_socket = self.clone()
        new_socket.socket = connection
        return (new_socket, address)

    def connect(self, address):
        self.socket.connect(address)

    def enqueue(self, data, addr):
        return self.msg_queue.put_nowait(0, data)

    def get(self, msg_seq=0, terminate=None, callback=None, noraise=False):
        '''Sync wrapper for async_get().'''

        async def collect_data():
            return [
                i
                async for i in self.async_get(
                    msg_seq, terminate, callback, noraise
                )
            ]

        return self.event_loop.run_until_complete(collect_data())

    async def async_get(
        self, msg_seq=0, terminate=None, callback=None, noraise=False
    ):
        '''Get a conversation answer from the socket.'''
        log.debug(
            "get: %s / %s / %s / %s", msg_seq, terminate, callback, noraise
        )
        enough = False
        started = False
        while not enough:
            data = await self.msg_queue.get(msg_seq)
            messages = tuple(self.marshal.parse(data, msg_seq, callback))
            if len(messages) == 0:
                break
            for msg in messages:
                if started and msg['header']['type'] == NLMSG_DONE:
                    return
                msg['header']['target'] = self.status['target']
                msg['header']['stats'] = Stats(0, 0, 0)
                started = True
                log.debug("yield %s", msg['header'])
                log.debug("message %s", msg)
                yield msg

            if started and (
                (msg_seq == 0)
                or (not msg['header'].get('flags', 0) & NLM_F_MULTI)
                or (callable(terminate) and terminate(msg))
            ):
                enough = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

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

    def register_policy(self, policy, msg_class=None):
        '''
        Register netlink encoding/decoding policy. Can
        be specified in two ways:
        `nlsocket.register_policy(MSG_ID, msg_class)`
        to register one particular rule, or
        `nlsocket.register_policy({MSG_ID1: msg_class})`
        to register several rules at once.
        E.g.::

            policy = {RTM_NEWLINK: ifinfmsg,
                      RTM_DELLINK: ifinfmsg,
                      RTM_NEWADDR: ifaddrmsg,
                      RTM_DELADDR: ifaddrmsg}
            nlsocket.register_policy(policy)

        One can call `register_policy()` as many times,
        as one want to -- it will just extend the current
        policy scheme, not replace it.
        '''
        if isinstance(policy, int) and msg_class is not None:
            policy = {policy: msg_class}

        if not isinstance(policy, dict):
            raise TypeError('wrong policy type')
        for key in policy:
            self.marshal.msg_map[key] = policy[key]

        return self.marshal.msg_map

    def unregister_policy(self, policy):
        '''
        Unregister policy. Policy can be:

            - int -- then it will just remove one policy
            - list or tuple of ints -- remove all given
            - dict -- remove policies by keys from dict

        In the last case the routine will ignore dict values,
        it is implemented so just to make it compatible with
        `get_policy_map()` return value.
        '''
        if isinstance(policy, int):
            policy = [policy]
        elif isinstance(policy, dict):
            policy = list(policy)

        if not isinstance(policy, (tuple, list, set)):
            raise TypeError('wrong policy type')

        for key in policy:
            del self.marshal.msg_map[key]

        return self.marshal.msg_map

    def get_policy_map(self, policy=None):
        '''
        Return policy for a given message type or for all
        message types. Policy parameter can be either int,
        or a list of ints. Always return dictionary.
        '''
        if policy is None:
            return self.marshal.msg_map

        if isinstance(policy, int):
            policy = [policy]

        if not isinstance(policy, (list, tuple, set)):
            raise TypeError('wrong policy type')

        ret = {}
        for key in policy:
            ret[key] = self.marshal.msg_map[key]

        return ret
