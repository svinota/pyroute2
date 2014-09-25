import io
import os
import struct
import socket
import threading

from pyroute2.iocore.addrpool import AddrPool  # FIXME: move to common
from pyroute2.netlink import nlmsg
from pyroute2.netlink import mtypes
from pyroute2.netlink import NetlinkError
from pyroute2.netlink import NetlinkDecodeError
from pyroute2.netlink import NetlinkHeaderDecodeError
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NETLINK_GENERIC


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

    def __init__(self, family=NETLINK_GENERIC, port=None, pid=None):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        global sockets

        # 8<-----------------------------------------
        # PID init is here only for compatibility,
        # later it will be completely moved to bind()
        self.epid = None
        self.port = 0
        self.fixed = True
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

    def bind(self, groups=0, pid=None):
        if pid is not None:
            self.port = 0
            self.fixed = True
            self.pid = pid or os.getpid()

        self.groups = groups
        # if we have pre-defined port, use it strictly
        if self.fixed:
            self.epid = self.pid + (self.port << 22)
            socket.socket.bind(self, (self.epid, self.groups))
            return

        # if we have no pre-defined port, scan all the
        # range till the first available port
        for i in range(1024):
            try:
                self.port = sockets.alloc()
                self.epid = self.pid + (self.port << 22)
                socket.socket.bind(self, (self.epid, self.groups))
                # if we're here, bind() done successfully, just exit
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
        if self.epid is not None:
            assert self.port is not None
            if not self.fixed:
                sockets.free(self.port)
            self.epid = None
        socket.socket.close(self)
