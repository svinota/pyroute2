import io
import os
import struct
import threading

from socket import AF_NETLINK
from socket import SOCK_DGRAM
from socket import MSG_PEEK
from socket import SOL_SOCKET
from socket import SO_RCVBUF
from socket import socket
from socket import error as SocketError

from pyroute2.iocore.addrpool import AddrPool  # FIXME: move to common
from pyroute2.common import DEFAULT_RCVBUF
from pyroute2.netlink import nlmsg
from pyroute2.netlink import mtypes
from pyroute2.netlink import NetlinkError
from pyroute2.netlink import NetlinkDecodeError
from pyroute2.netlink import NetlinkHeaderDecodeError
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NETLINK_GENERIC
from pyroute2.netlink import NLM_F_REQUEST


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
        self.defragmentation = {}

    def parse(self, data, sock=None):
        '''
        Parse the data in the buffer

        If socket is provided, support defragmentation
        '''
        with self.lock:
            data.seek(0)
            offset = 0
            result = []

            if sock in self.defragmentation:
                save = self.defragmentation[sock]
                save.write(data.read())
                save.length += data.length
                # discard save
                data = save
                del self.defragmentation[sock]
                data.seek(0)

            while offset < data.length:
                # pick type and length
                (length, msg_type) = struct.unpack('IH', data.read(6))
                data.seek(offset)
                # if length + offset is greater than
                # remaining size, save the buffer for
                # defragmentation
                if (sock is not None) and (length + offset > data.length):
                    # create save buffer
                    self.defragmentation[sock] = save = io.BytesIO()
                    save.length = save.write(data.read())
                    # truncate data
                    data.truncate(offset)
                    break

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
                    # try to decode encapsulated error message
                    if error is not None:
                        enc_type = struct.unpack('H', msg.raw[24:26])[0]
                        enc_class = self.msg_map.get(enc_type, nlmsg)
                        enc = enc_class(msg.raw[20:])
                        enc.decode()
                        msg['header']['errmsg'] = enc
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


# 8<-----------------------------------------------------------
# Singleton, containing possible modifiers to the NetlinkSocket
# bind() call.
#
# Normally, you can open only one netlink connection for one
# process, but there is a hack. Current PID_MAX_LIMIT is 2^22,
# so we can use the rest to midify pid field.
#
# See also libnl library, lib/socket.c:generate_local_port()
sockets = AddrPool(minaddr=0x0,
                   maxaddr=0x3ff,
                   reverse=True)
# 8<-----------------------------------------------------------


class NetlinkSocket(socket):
    '''
    Generic netlink socket
    '''

    def __init__(self, family=NETLINK_GENERIC, port=None, pid=None):
        socket.__init__(self, AF_NETLINK, SOCK_DGRAM, family)
        global sockets

        # 8<-----------------------------------------
        # PID init is here only for compatibility,
        # later it will be completely moved to bind()
        self.epid = None
        self.port = 0
        self.fixed = True
        self.backlog = {}
        self.lock = threading.Lock()
        if pid is None:
            self.pid = os.getpid() & 0x3fffff
            self.port = port
            self.fixed = self.port is not None
        elif pid == 0:
            self.pid = os.getpid()
        else:
            self.pid = pid
        # 8<-----------------------------------------
        self.groups = 0
        self.marshal = Marshal()

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

        assert isinstance(policy, dict)
        for key in policy:
            self.marshal.msg_map[key] = policy[key]

        return self.marshal.msg_map

    def unregister_policy(self, policy):
        '''
        Unregister policy. Policy can be:

        * int -- then it will just remove one policy
        * list or tuple of ints -- remove all given
        * dict -- remove policies by keys from dict

        In the last case the routine will ignore dict values,
        it is implemented so just to make it compatible with
        `get_policy_map()` return value.
        '''
        if isinstance(policy, int):
            policy = [policy]
        elif isinstance(policy, dict):
            policy = list(policy)

        assert isinstance(policy, (tuple, list, set))

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

        assert isinstance(policy, (list, tuple, set))

        ret = {}
        for key in policy:
            ret[key] = self.marshal.msg_map[key]

        return ret

    def bind(self, groups=0, pid=None):
        '''
        Bind the socket to given multicast groups, using
        given pid.

        * If pid is None, use automatic port allocation
        * If pid == 0, use process' pid
        * If pid == <int>, use the value instead of pid
        '''
        if pid is not None:
            self.port = 0
            self.fixed = True
            self.pid = pid or os.getpid()

        self.groups = groups
        # if we have pre-defined port, use it strictly
        if self.fixed:
            self.epid = self.pid + (self.port << 22)
            socket.bind(self, (self.epid, self.groups))
            return

        # if we have no pre-defined port, scan all the
        # range till the first available port
        for i in range(1024):
            try:
                self.port = sockets.alloc()
                self.epid = self.pid + (self.port << 22)
                socket.bind(self, (self.epid, self.groups))
                # if we're here, bind() done successfully, just exit
                return
            except SocketError as e:
                # pass occupied sockets, raise other exceptions
                if e.errno != 98:
                    raise
        else:
            # raise "address in use" -- to be compatible
            raise SocketError(98, 'Address already in use')

    def put(self, msg, msg_type,
            msg_flags=NLM_F_REQUEST,
            addr=(0, 0),
            msg_seq=0,
            msg_pid=None):
        '''
        Construct a message from a dictionary and send it to
        the socket. Parameters:

        * msg -- the message in the dictionary format
        * msg_type -- the message type
        * msg_flags -- the message flags to use in the request
        * addr -- `sendto()` addr, default `(0, 0)`
        * msg_seq -- sequence number to use
        * msg_pid -- pid to use, if `None` -- use os.getpid()

        Example::

            s = IPRSocket()
            s.bind()
            s.put({'index': 1}, RTM_GETLINK)
            s.get()
            s.close()

        Please notice, that the return value of `s.get()` can be
        not the result of `s.put()`, but any broadcast message.
        To fix that, use `msg_seq` -- the response must contain the
        same `msg['header']['sequence_number']` value.
        '''
        with self.lock:
            msg_class = self.marshal.msg_map[msg_type]
            if msg_pid is None:
                msg_pid = os.getpid()
            msg = msg_class(msg)
            msg['header']['type'] = msg_type
            msg['header']['flags'] = msg_flags
            msg['header']['sequence_number'] = msg_seq
            msg['header']['pid'] = msg_pid
            msg.encode()
            self.sendto(msg.buf.getvalue(), addr)

    def get(self, bufsize=DEFAULT_RCVBUF, msg_seq=None):
        '''
        Get parsed messages list. If `msg_seq` is given, return
        only messages with that `msg['header']['sequence_number']`,
        saving all other messages into `self.backlog`.

        The routine is thread-safe.

        The `bufsize` parameter can be:

        * -1: bufsize will be calculated from the first 4 bytes of
              the network data
        * 0: bufsize will be calculated from SO_RCVBUF sockopt
        * int >= 0: just a bufsize
        '''
        with self.lock:
            if bufsize == -1:
                # get bufsize from the network data
                bufsize = struct.unpack("I", self.recv(4, MSG_PEEK))[0]
            elif bufsize == 0:
                # get bufsize from SO_RCVBUF
                bufsize = self.getsockopt(SOL_SOCKET, SO_RCVBUF) // 2

            ret = []
            while not ret:
                if msg_seq is None and self.backlog:
                    # load backlog, if there is valid
                    # content in it
                    for key in tuple(self.backlog):
                        ret.extend(self.backlog[key])
                        del self.backlog[key]
                elif msg_seq in self.backlog:
                    ret.extend(self.backlog[msg_seq])
                    del self.backlog[msg_seq]
                    # now, if `ret` is not empty, the
                    # routine will exit (`while not ret`)
                else:
                    # if we are still missing messages to
                    # return, wait for them on the socket
                    data = io.BytesIO()
                    data.length = data.write(self.recv(bufsize))
                    msgs = self.marshal.parse(data, self)

                    # we have here a list of messages from
                    # the socket
                    if msg_seq is None:
                        # if all messages are requested, just
                        # extend the return list
                        ret.extend(msgs)
                    else:
                        # else -- save all into the backlog and
                        # return only the required sequence number
                        for msg in msgs:
                            seq = msg['header']['sequence_number']
                            if seq == msg_seq:
                                ret.append(msg)
                            else:
                                if seq not in self.backlog:
                                    self.backlog[seq] = []
                                self.backlog[seq].append(msg)
            return ret

    def close(self):
        '''
        Correctly close the socket and free all resources.
        '''
        global sockets
        if self.epid is not None:
            assert self.port is not None
            if not self.fixed:
                sockets.free(self.port)
            self.epid = None
        socket.close(self)
