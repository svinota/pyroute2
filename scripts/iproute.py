#!/usr/bin/python

import pprint
import threading
import select
import Queue
import io

from socket import AF_INET
from pyroute2.netlink.generic import nlsocket
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import NETLINK_ROUTE
from pyroute2.netlink.rtnl import marshal_rtnl
from pyroute2.netlink.rtmsg.ndmsg import ndmsg
from pyroute2.netlink.rtnl import RTNLGRP_IPV4_IFADDR
from pyroute2.netlink.rtnl import RTNLGRP_IPV6_IFADDR
from pyroute2.netlink.rtnl import RTNLGRP_IPV4_ROUTE
from pyroute2.netlink.rtnl import RTNLGRP_IPV6_ROUTE
from pyroute2.netlink.rtnl import RTNLGRP_LINK
from pyroute2.netlink.rtnl import RTNLGRP_NEIGH
from pyroute2.netlink.rtnl import RTM_GETNEIGH

## Netlink message flags values (nlmsghdr.flags)
#
NLM_F_REQUEST            = 1    # It is request message.
NLM_F_MULTI              = 2    # Multipart message, terminated by NLMSG_DONE
NLM_F_ACK                = 4    # Reply with ack, with zero or error code
NLM_F_ECHO               = 8    # Echo this request
# Modifiers to GET request
NLM_F_ROOT               = 0x100    # specify tree    root
NLM_F_MATCH              = 0x200    # return all matching
NLM_F_ATOMIC             = 0x400    # atomic GET
NLM_F_DUMP               = (NLM_F_ROOT|NLM_F_MATCH)
# Modifiers to NEW request
NLM_F_REPLACE            = 0x100    # Override existing
NLM_F_EXCL               = 0x200    # Do not touch, if it exists
NLM_F_CREATE             = 0x400    # Create, if it does not exist
NLM_F_APPEND             = 0x800    # Add to end of list

NLMSG_NOOP               = 0x1    # Nothing
NLMSG_ERROR              = 0x2    # Error
NLMSG_DONE               = 0x3    # End of a dump
NLMSG_OVERRUN            = 0x4    # Data lost
NLMSG_MIN_TYPE           = 0x10    # < 0x10: reserved control messages
NLMSG_MAX_LEN            = 0xffff# Max message length


class IpRoute(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.e = select.poll()
        self.socket = nlsocket(NETLINK_ROUTE)
        self.socket.bind(RTNLGRP_IPV4_IFADDR | RTNLGRP_IPV6_IFADDR |
                         RTNLGRP_IPV4_ROUTE | RTNLGRP_IPV6_ROUTE |
                         RTNLGRP_LINK )
        self.marshal = marshal_rtnl(self.socket)
        self.e.register(self.socket.fileno(), select.POLLIN)
        self.__nonce = 1
        # self.listeners = {0: Queue.Queue()}
        self.listeners = {}
        self.__stop = False
        self.start()

    def run(self):
        while not self.__stop:
            fds = self.e.poll()
            print(fds)
            for fd in fds:
                print(self.socket.fileno())
                if fd[0] == self.socket.fileno():
                    msg = self.marshal.recv()
                    key = msg['header']['sequence_number']
                    if key == 0:
                        continue
                    if key in self.listeners:
                        self.listeners[key].put(msg)
                    #if key != 0:
                    #    print("put %s into the queue %s" % (msg, 0))
                    #    self.listeners[0].put(msg)

    def stop(self):
        print("--------------------------------------- stop --------------")

    def nonce(self):
        """
        Increment netlink protocol nonce (there is no need to call it directly)
        """
        if self.__nonce == 0xffffffff:
            self.__nonce = 1
        else:
            self.__nonce += 1
        return self.__nonce

    def get(self, key=0, blocking=True):
        """
        Get a message from a queue
        """
        assert key in self.listeners

        result = []
        while True:
            msg = self.listeners[key].get()
            print("loaded message %s" % (msg))
            if msg['header']['flags'] & NLM_F_MULTI:
                result.append(msg)
            if msg['header']['type'] == NLMSG_DONE:
                break
        return result

    def get_all_neighbors(self):
        import os
        header = nlmsg()
        header['sequence_number'] = self.nonce()
        header['pid'] = os.getpid()
        self.listeners[header['sequence_number']] = Queue.Queue()
        header['type'] = RTM_GETNEIGH
        header['flags'] = NLM_F_DUMP | NLM_F_REQUEST
        msg = ndmsg()
        msg['family'] = AF_INET
        buf = io.BytesIO()
        header.buf = buf
        msg.buf = buf
        header.pack()
        msg.pack()
        l = buf.tell()
        buf.seek(0)
        import struct
        buf.write(struct.pack("I", l))
        self.socket.sendto(buf.getvalue(), (0, 0))
        return self.get(header['sequence_number'])

