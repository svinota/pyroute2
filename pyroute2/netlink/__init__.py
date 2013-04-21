import threading
import select
import Queue
import os
import io

from pyroute2.netlink.generic import nlsocket
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import NETLINK_GENERIC
from pyroute2.netlink.generic import marshal as mrsh


## Netlink message flags values (nlmsghdr.flags)
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
NLMSG_MIN_TYPE = 0x10    # < 0x10: reserved control messages
NLMSG_MAX_LEN = 0xffff  # Max message length

IPRCMD_NOOP = 1
IPRCMD_REGISTER = 2
IPRCMD_UNREGISTER = 3
IPRCMD_STOP = 4


class cmdmsg(nlmsg):
    fmt = "HHH"
    fields = ("command", "v1", "v2")


class netlink_io(threading.Thread):
    def __init__(self, marshal, family, groups):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.socket = nlsocket(family)
        self.socket.bind(groups)
        self.marshal = marshal(self.socket)
        self.listeners = {}
        self.poll = select.poll()
        (self.ctlr, self.control) = os.pipe()
        self.register(self.ctlr)
        self.register(self.socket)
        self.__stop = False

    def register(self, fd, mask=select.POLLIN):
        self.poll.register(fd, mask)

    def unregister(self, fd):
        self.poll.unregister(fd)

    def run(self):
        while not self.__stop:
            fds = self.poll.poll()
            for fd in fds:
                if fd[0] == self.ctlr:
                    buf = io.BytesIO()
                    buf.write(os.read(self.ctlr, 6))
                    buf.seek(0)
                    cmd = cmdmsg(buf)
                    if cmd['command'] == IPRCMD_REGISTER:
                        args = [cmd['v1'], ]
                        if cmd['v2'] > 0:
                            args.append(cmd['v2'])
                        self.register(args)
                    elif cmd['command'] == IPRCMD_UNREGISTER:
                        self.unregister(cmd['v1'])
                    elif cmd['command'] == IPRCMD_STOP:
                        self.__stop = True
                        break

                elif fd[0] == self.socket.fileno():
                    for msg in self.marshal.recv():
                        key = msg['header']['sequence_number']
                        if key in self.listeners:
                            self.listeners[key].put(msg)


class netlink(object):

    family = NETLINK_GENERIC
    groups = 0
    marshal = mrsh

    def __init__(self, debug=False):
        self.io_thread = netlink_io(self.marshal, self.family, self.groups)
        self.io_thread.start()
        self.listeners = self.io_thread.listeners
        self.socket = self.io_thread.socket
        self.debug = debug
        self.__nonce = 1

    def nonce(self):
        """
        Increment netlink protocol nonce (there is no need to call it directly)
        """
        if self.__nonce == 0xffffffff:
            self.__nonce = 1
        else:
            self.__nonce += 1
        return self.__nonce

    def monitor(self, operate=True):
        if operate:
            self.listeners[0] = Queue.Queue()
        else:
            del self.listeners[0]

    def stop(self):
        msg = cmdmsg(io.BytesIO())
        msg['command'] = IPRCMD_STOP
        msg.encode()
        os.write(self.io_thread.control, msg.buf.getvalue())

    def get(self, key=0, blocking=True):
        """
        Get a message from a queue
        """
        assert key in self.listeners

        result = []
        while True:
            msg = self.listeners[key].get()
            if msg['header']['type'] != NLMSG_DONE:
                result.append(msg)
            if (msg['header']['type'] == NLMSG_DONE) or \
               (not msg['header']['flags'] & NLM_F_MULTI):
                break
        return result

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST):
        nonce = self.nonce()
        self.listeners[nonce] = Queue.Queue()
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg.encode()
        self.socket.sendto(msg.buf.getvalue(), (0, 0))
        result = self.get(nonce)
        if not self.debug:
            for i in result:
                del i['header']
        return result
