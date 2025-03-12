import asyncio
import collections
import errno
import logging
import os
import socket
import struct
import threading
from dataclasses import asdict, dataclass
from typing import Optional, Type, Union
from urllib import parse

from pyroute2 import config, netns
from pyroute2.common import AddrPool
from pyroute2.netlink import NLM_F_MULTI
from pyroute2.requests.main import RequestFilter, RequestProcessor

MAGIC_CLOSE = 0x42
log = logging.getLogger(__name__)
Stats = collections.namedtuple('Stats', ('qsize', 'delta', 'delay'))
CoreSocketResources = collections.namedtuple(
    'CoreSocketResources',
    ('socket', 'msg_queue', 'event_loop', 'transport', 'protocol'),
)


class NoClose(socket.socket):
    def __init__(self, sock: socket.socket):
        self.magic = 0
        fd = os.dup(sock.fileno())
        sock.close()
        super().__init__(fileno=fd)

    def close(self):
        if self.magic == MAGIC_CLOSE:
            super().close()


@dataclass
class CoreConfig:
    target: str = 'localhost'
    flags: int = os.O_CREAT
    groups: int = 0
    rcvsize: int = 16384
    netns: Optional[str] = None
    tag_field: str = ''
    address: Optional[tuple[str, int]] = None
    use_socket: bool = False
    use_event_loop: bool = False
    use_libc: bool = False


class CoreSocketSpec:
    defaults: dict[str, Union[bool, int, str, None, tuple[str, ...]]] = {
        'closed': False,
        'compiled': None,
        'uname': config.uname,
    }
    status_filters: list[Type[RequestFilter]] = []

    def __init__(self, config: CoreConfig):
        self.config = config
        self.status = RequestProcessor()
        for flt in self.status_filters:
            self.status.add_filter(flt())
        self.status.update(self.defaults)
        self.status.update(asdict(self.config))

    def __setitem__(self, key, value):
        setattr(self.config, key, value)
        self.status.update(asdict(self.config))

    def __getitem__(self, key):
        return getattr(self.config, key)

    def serializable(self):
        return not any(
            (
                self.config.use_socket,
                self.config.use_event_loop,
                self.config.use_libc,
            )
        )


class CoreMessageQueue:

    def __init__(self, event_loop):
        # python versions < 3.11 require the event loop
        # to be running on Queue().__init__(), while
        # python 3.12+ bind the queue on get()/put()
        #
        # so we must require the event loop on __init__()
        # just to provide the compatibility.
        #
        self.event_loop = event_loop
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

    def ensure_tag(self, tag):
        if tag not in self.queues:
            self.queues[tag] = asyncio.Queue()

    def free_tag(self, tag):
        del self.queues[tag]

    def put_nowait(self, tag, message):
        if tag not in self.queues:
            tag = 0
        return self.queues[tag].put_nowait(message)


class CoreProtocol(asyncio.Protocol):
    def __init__(self, on_con_lost, enqueue, error_event, status):
        self.transport = None
        self.enqueue = enqueue
        self.on_con_lost = on_con_lost
        self.error_event = error_event
        self.status = status

    def connection_made(self, transport):
        self.transport = transport

    def enqueue_error(self, code: Optional[int]) -> None:
        if code is None:
            code = errno.ECOMM
        try:
            self.enqueue(struct.pack('IHHQIQQ', 28, 2, 0, 0, code, 0, 0), None)
        except AttributeError:
            # while closing, self.msg_queue can be removed already
            pass

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.on_con_lost.set_result(True)
        self.enqueue_error(errno.ECONNRESET)

    def error_received(self, exc: OSError) -> None:
        self.status['error'] = exc
        self.error_event.set()
        self.enqueue_error(exc.errno)


class CoreStreamProtocol(CoreProtocol):

    def data_received(self, data):
        log.debug('SOCK_STREAM enqueue %s bytes' % len(data))
        self.enqueue(data, None)


class CoreDatagramProtocol(CoreProtocol):

    def datagram_received(self, data, addr):
        log.debug('SOCK_DGRAM enqueue %s bytes' % len(data))
        self.enqueue(data, addr)


class AsyncCoreSocket:
    '''Pyroute2 core socket class.

    This class implements the core socket concept for all the pyroute2
    communications, both Netlink and internal RPC.

    The asynchronous version is the most basic. All the sync classes
    are built on top of it.
    '''

    compiled = None
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
        use_event_loop=None,
    ):
        # 8<-----------------------------------------
        self.spec = CoreSocketSpec(
            CoreConfig(
                target=target,
                rcvsize=rcvsize,
                netns=netns,
                flags=flags,
                groups=groups,
                use_libc=libc is not None,
                use_socket=use_socket is not None,
                use_event_loop=use_event_loop is not None,
            )
        )
        self.status = self.spec.status
        self.status['eids'] = set()
        self.local = threading.local()
        self.lock = threading.Lock()
        self.libc = libc
        self.use_socket = use_socket
        self.use_event_loop = use_event_loop
        self.request_proxy = None
        self._tid = threading.get_ident()
        self._error_event = threading.Event()
        url = parse.urlparse(self.spec['target'])
        self.scheme = url.scheme if url.scheme else url.path
        self.callbacks = []  # [(predicate, callback, args), ...]
        self.addr_pool = AddrPool(minaddr=0x000000FF, maxaddr=0x0000FFFF)
        self.marshal = None
        self.buffer = []
        self.msg_reschedule = []
        self.__open_sockets = set()
        self.__open_resources = set()
        self.__msg_queues = set()

    def _check_tid(self, call: str = '', ext: Optional[str] = None):
        if self._tid != threading.get_ident():
            if ext is None:
                ext = f'calling ${call}() is not allowed from another thread'
            raise RuntimeError(ext)

    def _register_loop_ref(self):
        self.__open_resources.add((self.event_loop, self.msg_queue))

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
        else:
            log.debug(
                'preventing override of marshal %s with %s',
                self.__marshal,
                value,
            )

    def set_marshal(self, value):
        self.__marshal = value

    # 8<--------------------------------------------------------------
    # Thread local section
    @property
    def msg_queue(self):
        return self.local.msg_queue

    @property
    def connection_lost(self):
        if self._error_event.is_set():
            raise self.status['error']
        if not hasattr(self.local, 'connection_lost'):
            self.local.connection_lost = self.event_loop.create_future()
        return self.local.connection_lost

    @property
    def socket(self):
        if self._error_event.is_set():
            raise self.status['error']
        if not hasattr(self.local, 'prime'):
            self.local.prime = self.setup_socket()
        if not hasattr(self.local, 'socket'):
            self.local.msg_queue = CoreMessageQueue(event_loop=self.event_loop)
            self.__msg_queues.add(self.local.msg_queue)
            self.local.socket = NoClose(self.local.prime)
            self.__open_sockets.add(self.local.socket)
            # 8<-----------------------------------------
            # Mock netlink
            if self.spec['netns'] is not None and config.mock_netlink:
                self.local.socket.netns = self.spec['netns']
                self.local.socket.flags = self.spec['flags']
                self.local.socket.initdb()
        return self.local.socket

    @property
    def event_loop(self):
        if self._error_event.is_set():
            raise self.status['error']
        if not hasattr(self.local, 'event_loop'):
            if self.status['use_event_loop']:
                self._check_tid(
                    ext='Predefined event loop can not be used '
                    'in another thread'
                )
            self.local.event_loop = self.setup_event_loop()
        if self.local.event_loop.is_closed():
            raise OSError(errno.EBADF, 'Bad file descriptor')
        return self.local.event_loop

    @property
    def transport(self):
        return self.local.transport

    @property
    def protocol(self):
        if not hasattr(self.local, 'protocol'):
            self.local.protocol = None
        return self.local.protocol

    #
    # 8<--------------------------------------------------------------
    #
    def setup_event_loop(self):
        try:
            event_loop = asyncio.get_running_loop()
            self.status['event_loop'] = 'auto'
        except RuntimeError:
            event_loop = asyncio.new_event_loop()
            self.status['event_loop'] = 'new'
            self.status['eids'].add(id(event_loop))
        return event_loop

    def setup_socket(self):
        if self.use_socket is not None:
            return self.use_socket
        sock = netns.create_socket(
            self.spec['netns'],
            socket.AF_INET,
            socket.SOCK_STREAM,
            flags=self.spec['flags'],
            libc=self.libc,
        )
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    async def setup_endpoint(self):
        # Setup asyncio
        if self.transport is not None:
            return
        self.local.transport, self.local.protocol = (
            await self.event_loop.connect_accepted_socket(
                lambda: CoreStreamProtocol(
                    self.connection_lost,
                    self.enqueue,
                    self._error_event,
                    self.status,
                ),
                sock=self.socket,
            )
        )

    # 8<--------------------------------------------------------------

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

    async def bind(self, addr):
        '''Bind the socket to the address.'''
        await self.setup_endpoint()
        return self.socket.bind(addr)

    def close(self, code=errno.ECONNRESET):
        '''Terminate the object.'''

        def send_terminator(msg_queue):
            msg_queue.put_nowait(0, b'')

        with self.lock:
            for event_loop, msg_queue in self.__open_resources:
                if not event_loop.is_closed():
                    event_loop.call_soon_threadsafe(send_terminator, msg_queue)
            if hasattr(self.local, 'transport'):
                self.local.transport.abort()
                self.local.transport.close()
                del self.local.transport
                del self.local.protocol
            if self.status['event_loop'] == 'new':
                if (
                    hasattr(self.local, 'event_loop')
                    and not self.local.event_loop.is_closed()
                ):
                    self.event_loop.run_until_complete(
                        self.event_loop.shutdown_asyncgens()
                    )
                    self.event_loop.stop()
                    self.event_loop.close()
                    del self.local.event_loop
            for sock in tuple(self.__open_sockets):
                sock.magic = MAGIC_CLOSE
                sock.close()

    def clone(self):
        '''Return a copy of itself with a new underlying socket.

        This method can not work if `use_socket` or `event_loop`
        was used in the object constructor.'''
        if self.status['use_socket'] or self.status['event_loop']:
            raise RuntimeError('can not clone socket')
        new_spec = {}
        for key, value in self.spec.items():
            if key in self.__init__.__code__.co_varnames:
                new_spec[key] = value
        return type(self)(**new_spec)

    def setsockopt(self, level, optname, value):
        return self.socket.setsockopt(level, optname, value)

    def getsockopt(self, level, optname):
        return self.socket.getsockopt(level, optname)

    def recv(self, buffersize, flags=0):
        '''Get one buffer from the socket.'''
        return self.socket.recv(buffersize, flags)

    def send(self, data, flags=0):
        '''Send one buffer via the socket.'''
        return self.socket.send(data, flags)

    def accept(self):
        if self.use_socket is not None:
            return (self, None)
        (connection, address) = self.socket.accept()
        new_socket = self.clone()
        new_socket.socket = connection
        return (new_socket, address)

    def connect(self, address):
        self.socket.connect(address)

    def enqueue(self, data, addr):
        return self.msg_queue.put_nowait(0, data)

    async def get(
        self, msg_seq=0, terminate=None, callback=None, noraise=False
    ):
        '''Get a conversation answer from the socket.'''
        await self.setup_endpoint()
        log.debug(
            "get: %s / %s / %s / %s", msg_seq, terminate, callback, noraise
        )
        if msg_seq == -1:
            msg_seq = 0
        enough = False
        started = False
        error = None
        while not enough:
            log.debug('await data on %s', self.msg_queue)
            data = await self.msg_queue.get(msg_seq)
            messages = tuple(self.marshal.parse(data, msg_seq, callback))
            if len(messages) == 0:
                break
            for msg in messages:
                log.debug("message %s", msg)
                if msg.get('header', {}).get('error') is not None:
                    error = msg['header']['error']
                    enough = True
                    break
                if self.marshal.is_enough(msg):
                    enough = True
                    break
                msg['header']['target'] = self.status['target']
                msg['header']['stats'] = Stats(0, 0, 0)
                started = True
                log.debug("yield %s", msg['header'])
                yield msg

            if started and (
                (msg_seq == 0)
                or (not msg['header'].get('flags', 0) & NLM_F_MULTI)
                or (callable(terminate) and terminate(msg))
            ):
                enough = True
        if not noraise and error:
            raise error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
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


class SyncAPI:
    '''
    Synchronous API wrapper around asynchronous classes
    '''

    @property
    def marshal(self):
        return self.asyncore.marshal

    @marshal.setter
    def marshal(self, value):
        self.asyncore.marshal = value

    def set_marshal(self, value):
        return self.asyncore.set_marshal(value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __getattr__(self, key):
        if key in (
            'pid',
            'spec',
            'status',
            'send',
            'recv',
            'lock',
            'sendto',
            'setsockopt',
            'getsockopt',
            'register_policy',
            'unregister_policy',
        ):
            return getattr(self.asyncore, key)
        raise AttributeError(key)

    @property
    def fileno(self):
        return self.asyncore.socket.fileno

    def _setup_transport(self):
        if hasattr(self.asyncore.local, 'event_loop'):
            return
        self.asyncore.event_loop.run_until_complete(
            self.asyncore.setup_endpoint()
        )

    def _cleanup_transport(self) -> None:
        if hasattr(self.asyncore.local, 'keep_event_loop'):
            return
        self.asyncore.transport.abort()
        self.asyncore.transport.close()
        self.asyncore.event_loop.run_until_complete(
            self.asyncore.event_loop.shutdown_asyncgens()
        )
        self.asyncore.event_loop.stop()
        self.asyncore.event_loop.close()
        del self.asyncore.local.transport
        del self.asyncore.local.connection_lost
        del self.asyncore.local.event_loop

    def _one_time_loop(self, func, *argv, **kwarg):
        self._setup_transport()
        ret = self.asyncore.event_loop.run_until_complete(func(*argv, **kwarg))
        self._cleanup_transport()
        return ret

    def mock_data(self, data):
        if getattr(self.asyncore.local, 'msg_queue', None) is None:
            self.asyncore.local.msg_queue = CoreMessageQueue(
                event_loop=self.event_loop
            )
        self.asyncore.msg_queue.put_nowait(0, data)

    def close(self, code=errno.ECONNRESET):
        '''Correctly close the socket and free all the resources.'''
        self.asyncore.close(code)


class CoreSocket(SyncAPI):
    def __init__(
        self,
        target='localhost',
        rcvsize=16384,
        use_socket=False,
        netns=None,
        flags=os.O_CREAT,
        libc=None,
        groups=0,
    ):
        self.asyncore = AsyncCoreSocket(
            target, rcvsize, use_socket, netns, flags, libc, groups
        )
