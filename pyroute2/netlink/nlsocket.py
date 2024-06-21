'''
Base netlink socket and marshal
===============================

All the netlink providers are derived from the socket
class, so they provide normal socket API, including
`getsockopt()`, `setsockopt()`, they can be used in
poll/select I/O loops etc.

asynchronous I/O
----------------

To run async reader thread, one should call
`NetlinkSocket.bind(async_cache=True)`. In that case
a background thread will be launched. The thread will
automatically collect all the messages and store
into a userspace buffer.

.. note::
    There is no need to turn on async I/O, if you
    don't plan to receive broadcast messages.

ENOBUF and async I/O
--------------------

When Netlink messages arrive faster than a program
reads then from the socket, the messages overflow
the socket buffer and one gets ENOBUF on `recv()`::

    ... self.recv(bufsize)
    error: [Errno 105] No buffer space available

One way to avoid ENOBUF, is to use async I/O. Then the
library not only reads and buffers all the messages, but
also re-prioritizes threads. Suppressing the parser
activity, the library increases the response delay, but
spares CPU to read and enqueue arriving messages as
fast, as it is possible.

With logging level DEBUG you can notice messages, that
the library started to calm down the parser thread::

    DEBUG:root:Packet burst: the reader thread priority
        is increased, beware of delays on netlink calls
        Counters: delta=25 qsize=25 delay=0.1

This state requires no immediate action, but just some
more attention. When the delay between messages on the
parser thread exceeds 1 second, DEBUG messages become
WARNING ones::

    WARNING:root:Packet burst: the reader thread priority
        is increased, beware of delays on netlink calls
        Counters: delta=2525 qsize=213536 delay=3

This state means, that almost all the CPU resources are
dedicated to the reader thread. It doesn't mean, that
the reader thread consumes 100% CPU -- it means, that the
CPU is reserved for the case of more intensive bursts. The
library will return to the normal state only when the
broadcast storm will be over, and then the CPU will be
100% loaded with the parser for some time, when it will
process all the messages queued so far.

when async I/O doesn't help
---------------------------

Sometimes, even turning async I/O doesn't fix ENOBUF.
Mostly it means, that in this particular case the Python
performance is not enough even to read and store the raw
data from the socket. There is no workaround for such
cases, except of using something *not* Python-based.

One can still play around with SO_RCVBUF socket option,
but it doesn't help much. So keep it in mind, and if you
expect massive broadcast Netlink storms, perform stress
testing prior to deploy a solution in the production.

classes
-------
'''

import collections
import errno
import logging
import multiprocessing
import os
import random
import struct
import time
from socket import SO_RCVBUF, SO_SNDBUF, SOCK_DGRAM, SOL_SOCKET, socketpair

from pyroute2 import config
from pyroute2.common import AddrPool, basestring
from pyroute2.config import AF_NETLINK
from pyroute2.netlink import (
    NETLINK_ADD_MEMBERSHIP,
    NETLINK_DROP_MEMBERSHIP,
    NETLINK_EXT_ACK,
    NETLINK_GENERIC,
    NETLINK_GET_STRICT_CHK,
    NETLINK_LISTEN_ALL_NSID,
    NLM_F_ACK,
    NLM_F_APPEND,
    NLM_F_CREATE,
    NLM_F_DUMP,
    NLM_F_DUMP_INTR,
    NLM_F_ECHO,
    NLM_F_EXCL,
    NLM_F_REPLACE,
    NLM_F_REQUEST,
    SOL_NETLINK,
    nlmsg,
)
from pyroute2.netlink.core import (
    CoreDatagramProtocol,
    CoreSocket,
    CoreSocketSpec,
)
from pyroute2.netlink.exceptions import (
    ChaoticException,
    NetlinkDumpInterrupted,
    NetlinkError,
)
from pyroute2.netlink.marshal import Marshal
from pyroute2.plan9.client import Plan9Client

log = logging.getLogger(__name__)


class CompileContext:
    def __init__(self, netlink_socket):
        self.netlink_socket = netlink_socket
        self.netlink_socket.compiled = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.netlink_socket.compiled = None


# 8<-----------------------------------------------------------
# Singleton, containing possible modifiers to the NetlinkSocket
# bind() call.
#
# Normally, you can open only one netlink connection for one
# process, but there is a hack. Current PID_MAX_LIMIT is 2^22,
# so we can use the rest to modify the pid field.
#
# See also libnl library, lib/socket.c:generate_local_port()
sockets = AddrPool(minaddr=0x0, maxaddr=0x3FF, reverse=True)
# 8<-----------------------------------------------------------


class NetlinkSocketSpecFilter:
    def set_pid(self, context, value):
        if value is None:
            return {'pid': os.getpid() & 0x3FFFFF, 'port': context['port']}
        elif value == 0:
            return {'pid': os.getpid()}
        else:
            return {'pid': value}

    def set_port(self, context, value):
        if isinstance(value, int):
            return {'port': value, 'epid': context['pid'] + (value << 22)}


class NetlinkSocketSpec(CoreSocketSpec):
    def __init__(self, spec=None):
        super().__init__(spec)
        default = {'pid': 0, 'epid': 0, 'port': 0, 'uname': config.uname}
        self.status.set_filter(NetlinkSocketSpecFilter())
        self.status.update(default)
        self.status.update(self)


class NetlinkSocket(CoreSocket):
    '''
    Netlink socket
    '''

    def __init__(
        self,
        family=NETLINK_GENERIC,
        port=None,
        pid=None,
        fileno=None,
        sndbuf=1048576,
        rcvbuf=1048576,
        rcvsize=16384,
        all_ns=False,
        async_qsize=None,
        nlm_generator=None,
        target='localhost',
        ext_ack=False,
        strict_check=False,
        groups=0,
        nlm_echo=False,
        use_socket=None,
        netns=None,
        flags=os.O_CREAT,
        libc=None,
    ):
        # 8<-----------------------------------------
        self.spec = NetlinkSocketSpec(
            {
                'family': family,
                'port': port,
                'pid': pid,
                'fileno': fileno,
                'sndbuf': sndbuf,
                'rcvbuf': rcvbuf,
                'rcvsize': rcvsize,
                'all_ns': all_ns,
                'async_qsize': async_qsize,
                'target': target,
                'nlm_generator': True,
                'ext_ack': ext_ack,
                'strict_check': strict_check,
                'groups': groups,
                'nlm_echo': nlm_echo,
                'use_socket': use_socket is not None,
                'tag_field': 'sequence_number',
                'netns': netns,
                'flags': flags,
            }
        )
        # TODO: merge capabilities to self.status
        self.capabilities = {
            'create_bridge': config.kernel > [3, 2, 0],
            'create_bond': config.kernel > [3, 2, 0],
            'create_dummy': True,
            'provide_master': config.kernel[0] > 2,
        }
        super().__init__(libc=libc)
        self.marshal = Marshal()

    async def setup_endpoint(self, loop=None):
        # Setup asyncio
        if self.endpoint is not None:
            return
        self.endpoint = await self.event_loop.create_datagram_endpoint(
            lambda: CoreDatagramProtocol(self.connection_lost, self.enqueue),
            sock=self.socket,
        )

    @property
    def uname(self):
        return self.status['uname']

    @property
    def groups(self):
        return self.status['groups']

    @property
    def port(self):
        return self.status['port']

    @property
    def pid(self):
        return self.status['pid']

    @property
    def target(self):
        return self.status['target']

    def setup_socket(self, sock=None):
        """Re-init a netlink socket."""
        if self.status['use_socket']:
            return self.use_socket
        sock = self.socket if sock is None else sock
        if sock is not None:
            sock.close()
        sock = config.SocketBase(
            AF_NETLINK, SOCK_DGRAM, self.spec['family'], self.spec['fileno']
        )
        sock.setsockopt(SOL_SOCKET, SO_SNDBUF, self.status['sndbuf'])
        sock.setsockopt(SOL_SOCKET, SO_RCVBUF, self.status['rcvbuf'])
        if self.status['ext_ack']:
            sock.setsockopt(SOL_NETLINK, NETLINK_EXT_ACK, 1)
        if self.status['all_ns']:
            sock.setsockopt(SOL_NETLINK, NETLINK_LISTEN_ALL_NSID, 1)
        if self.status['strict_check']:
            sock.setsockopt(SOL_NETLINK, NETLINK_GET_STRICT_CHK, 1)

        class Bala:
            def __init__(self, sock):
                self._socket = sock

            def ignore(self, *argv, **kwarg):
                print("ignore close")
                import traceback

                traceback.print_stack()

            def __getattr__(self, attr):
                if attr == 'close':
                    return self.ignore
                return getattr(self._socket, attr)

        return Bala(sock)

    def bind(self, groups=0, pid=None, **kwarg):
        '''
        Bind the socket to given multicast groups, using
        given pid.

            - If pid is None, use automatic port allocation
            - If pid == 0, use process' pid
            - If pid == <int>, use the value instead of pid
        '''

        self.status['groups'] = groups
        # if we have pre-defined port, use it strictly
        if self.status.get('port') is not None:
            self.socket.bind((self.status['epid'], self.status['groups']))
        else:
            for port in range(1024):
                try:
                    self.status['port'] = port
                    self.socket.bind(
                        (self.status['epid'], self.status['groups'])
                    )
                    break
                except Exception as e:
                    # create a new underlying socket -- on kernel 4
                    # one failed bind() makes the socket useless
                    log.error(e)
                    self.restart_base_socket()
            else:
                raise KeyError('no free address available')

    def add_membership(self, group):
        self.socket.setsockopt(SOL_NETLINK, NETLINK_ADD_MEMBERSHIP, group)

    def drop_membership(self, group):
        self.socket.setsockopt(SOL_NETLINK, NETLINK_DROP_MEMBERSHIP, group)

    def make_request_type(self, command, command_map):
        if isinstance(command, basestring):
            return (lambda x: (x[0], self.make_request_flags(x[1])))(
                command_map[command]
            )
        elif isinstance(command, int):
            return command, self.make_request_flags('create')
        elif isinstance(command, (list, tuple)):
            return command
        else:
            raise TypeError('allowed command types: int, str, list, tuple')

    def make_request_flags(self, mode):
        flags = {
            'dump': NLM_F_REQUEST | NLM_F_DUMP,
            'get': NLM_F_REQUEST | NLM_F_ACK,
            'req': NLM_F_REQUEST | NLM_F_ACK,
        }
        flags['create'] = flags['req'] | NLM_F_CREATE | NLM_F_EXCL
        flags['append'] = flags['req'] | NLM_F_CREATE | NLM_F_APPEND
        flags['change'] = flags['req'] | NLM_F_REPLACE
        flags['replace'] = flags['change'] | NLM_F_CREATE

        return flags[mode] | (
            NLM_F_ECHO
            if (self.status['nlm_echo'] and mode not in ('get', 'dump'))
            else 0
        )

    def enqueue(self, data, addr):
        # calculate msg_seq
        tag = struct.unpack_from('I', data, 8)[0]
        return self.msg_queue.put_nowait(tag, data)

    def put(
        self,
        msg,
        msg_type=0,
        msg_flags=NLM_F_REQUEST,
        addr=(0, 0),
        msg_seq=0,
        msg_pid=None,
    ):
        if not isinstance(msg, nlmsg):
            msg_class = self.marshal.msg_map[msg_type]
            msg = msg_class(msg)
        if msg_pid is None:
            msg_pid = self.status['epid'] or os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg['header']['sequence_number'] = msg_seq
        msg['header']['pid'] = msg_pid
        msg.reset()
        msg.encode()
        self.msg_queue.ensure(msg_seq)
        return self.send(msg.data)

    def compile(self):
        return CompileContext(self)

    def _send_batch(self, msgs, addr=(0, 0)):
        with self.backlog_lock:
            for msg in msgs:
                self.backlog[msg['header']['sequence_number']] = []
        # We have locked the message locks in the caller already.
        data = bytearray()
        for msg in msgs:
            if not isinstance(msg, nlmsg):
                msg_class = self.marshal.msg_map[msg['header']['type']]
                msg = msg_class(msg)
            msg.reset()
            msg.encode()
            data += msg.data
        if self.compiled is not None:
            return self.compiled.append(data)
        self._sock.sendto(data, addr)

    def nlm_request_batch(self, msgs, noraise=False):
        """
        This function is for messages which are expected to have side effects.
        Do not blindly retry in case of errors as this might duplicate them.
        """
        expected_responses = []
        acquired = 0
        seqs = self.addr_pool.alloc_multi(len(msgs))
        try:
            for seq in seqs:
                self.lock[seq].acquire()
                acquired += 1
            for seq, msg in zip(seqs, msgs):
                msg['header']['sequence_number'] = seq
                if 'pid' not in msg['header']:
                    msg['header']['pid'] = self.epid or os.getpid()
                if (msg['header']['flags'] & NLM_F_ACK) or (
                    msg['header']['flags'] & NLM_F_DUMP
                ):
                    expected_responses.append(seq)
            self._send_batch(msgs)
            if self.compiled is not None:
                for data in self.compiled:
                    yield data
            else:
                for seq in expected_responses:
                    for msg in self.get(msg_seq=seq, noraise=noraise):
                        if msg['header']['flags'] & NLM_F_DUMP_INTR:
                            # Leave error handling to the caller
                            raise NetlinkDumpInterrupted()
                        yield msg
        finally:
            # Release locks in reverse order.
            for seq in seqs[acquired - 1 :: -1]:
                self.lock[seq].release()

            with self.backlog_lock:
                for seq in seqs:
                    # Clear the backlog. We may have raised an error
                    # causing the backlog to not be consumed entirely.
                    if seq in self.backlog:
                        del self.backlog[seq]
                    self.addr_pool.free(seq, ban=0xFF)

    def nlm_request(
        self,
        msg,
        msg_type,
        msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
        terminate=None,
        callback=None,
        parser=None,
    ):
        msg_seq = self.addr_pool.alloc()
        defer = None
        if callable(parser):
            self.marshal.seq_map[msg_seq] = parser
        retry_count = 0
        try:
            while True:
                try:
                    self.put(msg, msg_type, msg_flags, msg_seq=msg_seq)
                    if self.compiled is not None:
                        for data in self.compiled:
                            yield data
                    else:
                        for msg in self.get(
                            msg_seq=msg_seq,
                            terminate=terminate,
                            callback=callback,
                        ):
                            # analyze the response for effects to be
                            # deferred
                            if (
                                defer is None
                                and msg['header']['flags'] & NLM_F_DUMP_INTR
                            ):
                                defer = NetlinkDumpInterrupted()
                            yield msg
                    break
                except NetlinkError as e:
                    if e.code != errno.EBUSY:
                        raise
                    if retry_count >= 30:
                        raise
                    log.warning('Error 16, retry {}.'.format(retry_count))
                    time.sleep(0.3)
                    retry_count += 1
                    continue
                except Exception:
                    raise
        finally:
            # Ban this msg_seq for 0xff rounds
            #
            # It's a long story. Modern kernels for RTM_SET.*
            # operations always return NLMSG_ERROR(0) == success,
            # even not setting NLM_F_MULTI flag on other response
            # messages and thus w/o any NLMSG_DONE. So, how to detect
            # the response end? One can not rely on NLMSG_ERROR on
            # old kernels, but we have to support them too. Ty, we
            # just ban msg_seq for several rounds, and NLMSG_ERROR,
            # being received, will become orphaned and just dropped.
            #
            # Hack, but true.
            self.addr_pool.free(msg_seq, ban=0xFF)
            if msg_seq in self.marshal.seq_map:
                self.marshal.seq_map.pop(msg_seq)
        if defer is not None:
            raise defer


IPCSocketPair = collections.namedtuple('IPCSocketPair', ('server', 'client'))


class IPCSocket(NetlinkSocket):

    def setup_socket(self):
        # create socket pair
        sp = IPCSocketPair(*socketpair())
        # start the server
        self.socket = sp
        self.p9server = multiprocessing.Process(target=self.ipc_server)
        self.p9server.daemon = True
        self.p9server.start()
        # create and init the client
        self.p9client = Plan9Client(use_socket=sp.client)
        self.p9client.init()
        return sp

    def ipc_server(self):
        raise NotImplementedError()

    def recv(self, buffersize, flags=0):
        ret = self.p9client.call(
            fid=self.p9client.fid('call'),
            fname='recv',
            kwarg={'buffersize': buffersize, 'flags': flags},
        )
        return ret['data']

    def send(self, data, flags=0):
        return self.p9client.call(
            fid=self.p9client.fid('call'),
            fname='send',
            kwarg={'flags': flags},
            data=data,
        )

    def bind(self):
        return self.p9client.call(fid=self.p9client.fid('call'), fname='bind')

    def close(self):
        self.socket.client.close()
        self.socket.server.close()
        self.p9server.wait()


class BatchAddrPool:
    def alloc(self, *argv, **kwarg):
        return 0

    def free(self, *argv, **kwarg):
        pass


class BatchBacklogQueue(list):
    def append(self, *argv, **kwarg):
        pass

    def pop(self, *argv, **kwarg):
        pass


class BatchBacklog(dict):
    def __getitem__(self, key):
        return BatchBacklogQueue()

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass


class BatchSocket(NetlinkSocket):
    def post_init(self):
        self.backlog = BatchBacklog()
        self.addr_pool = BatchAddrPool()
        self._sock = None
        self.reset()

    def reset(self):
        self.batch = bytearray()

    def nlm_request(
        self,
        msg,
        msg_type,
        msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
        terminate=None,
        callback=None,
    ):
        msg_seq = self.addr_pool.alloc()
        msg_pid = self.epid or os.getpid()

        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg['header']['sequence_number'] = msg_seq
        msg['header']['pid'] = msg_pid
        msg.data = self.batch
        msg.offset = len(self.batch)
        msg.encode()
        return []

    def get(self, *argv, **kwarg):
        pass


class ChaoticNetlinkSocket(NetlinkSocket):
    success_rate = 1

    def __init__(self, *argv, **kwarg):
        self.success_rate = kwarg.pop('success_rate', 0.7)
        super(ChaoticNetlinkSocket, self).__init__(*argv, **kwarg)

    def get(self, *argv, **kwarg):
        if random.random() > self.success_rate:
            raise ChaoticException()
        return super(ChaoticNetlinkSocket, self).get(*argv, **kwarg)
