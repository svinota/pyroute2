import threading
import struct
import socket
import os
import io

from pyroute2.iocore.addrpool import AddrPool  # FIXME: move to common
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import NetlinkDecodeError
from pyroute2.netlink.generic import NetlinkHeaderDecodeError
from pyroute2.netlink.generic import NETLINK_GENERIC


class NetlinkError(Exception):
    '''
    Base netlink error
    '''
    def __init__(self, code, msg=None):
        msg = msg or os.strerror(code)
        super(NetlinkError, self).__init__(code, msg)
        self.code = code


# Netlink message flags values (nlmsghdr.flags)
#
NLM_F_REQUEST = 1    # It is request message.
NLM_F_MULTI = 2    # Multipart message, terminated by NLMSG_DONE
NLM_F_ACK = 4    # Reply with ack, with zero or error code
NLM_F_ECHO = 8    # Echo this request
# Modifiers to GET request
NLM_F_ROOT = 0x100    # specify tree    root
NLM_F_MATCH = 0x200    # return all matching
NLM_F_ATOMIC = 0x400    # atomic GET
NLM_F_DUMP = (NLM_F_ROOT | NLM_F_MATCH)
# Modifiers to NEW request
NLM_F_REPLACE = 0x100    # Override existing
NLM_F_EXCL = 0x200    # Do not touch, if it exists
NLM_F_CREATE = 0x400    # Create, if it does not exist
NLM_F_APPEND = 0x800    # Add to end of list

NLMSG_NOOP = 0x1    # Nothing
NLMSG_ERROR = 0x2    # Error
NLMSG_DONE = 0x3    # End of a dump
NLMSG_OVERRUN = 0x4    # Data lost
NLMSG_CONTROL = 0xe    # Custom message type for messaging control
NLMSG_TRANSPORT = 0xf    # Custom message type for NL as a transport
NLMSG_MIN_TYPE = 0x10    # < 0x10: reserved control messages
NLMSG_MAX_LEN = 0xffff  # Max message length

mtypes = {1: 'NLMSG_NOOP',
          2: 'NLMSG_ERROR',
          3: 'NLMSG_DONE',
          4: 'NLMSG_OVERRUN'}

IPRCMD_NOOP = 0
IPRCMD_STOP = 1
IPRCMD_ACK = 2
IPRCMD_ERR = 3
IPRCMD_REGISTER = 4
IPRCMD_RELOAD = 5
IPRCMD_ROUTE = 6
IPRCMD_CONNECT = 7
IPRCMD_DISCONNECT = 8
IPRCMD_SERVE = 9
IPRCMD_SHUTDOWN = 10
IPRCMD_SUBSCRIBE = 11
IPRCMD_UNSUBSCRIBE = 12
IPRCMD_PROVIDE = 13
IPRCMD_REMOVE = 14
IPRCMD_DISCOVER = 15
IPRCMD_UNREGISTER = 16


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


class NetlinkSocket(socket.socket):
    '''
    Generic netlink socket
    '''

    def __init__(self, family=NETLINK_GENERIC, port=None):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        global sockets
        self.pid = os.getpid() & 0x3fffff
        self.port = port
        self.fixed = self.port is not None
        self.groups = 0
        self.marshal = None
        self.bound = False

    def bind(self, groups=0):
        self.groups = groups
        # if we have pre-defined port, use it strictly
        if self.fixed:
            socket.socket.bind(self, (self.pid + (self.port << 22),
                               self.groups))
            return

        # if we have no pre-defined port, scan all the
        # range till the first available port
        for i in range(1024):
            try:
                self.port = sockets.alloc()
                socket.socket.bind(self,
                                   (self.pid + (self.port << 22),
                                    self.groups))
                # if we're here, bind() done successfully, just exit
                self.bound = True
                return
            except socket.error as e:
                # pass occupied sockets, raise other exceptions
                if e.errno != 98:
                    raise
        else:
            # raise "address in use" -- to be compatible
            raise socket.error(98, 'Address already in use')

    def get(self):
        data = io.BytesIO()
        data.length = data.write(self.recv(16384))
        return self.marshal.parse(data)

    def close(self):
        global sockets
        if self.bound:
            assert self.port is not None
            if not self.fixed:
                sockets.free(self.port)
        socket.socket.close(self)
