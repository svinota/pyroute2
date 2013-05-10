import traceback
import threading
import urlparse
import select
import struct
import socket
import Queue
import copy
import time
import os
import io
import uuid
import ssl

from pyroute2.netlink.generic import ctrlmsg
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import NETLINK_GENERIC
from pyroute2.netlink.generic import NETLINK_UNUSED


def _monkey_handshake(self):
    ##
    #
    # We have to close incoming connection on handshake error.
    # But if the handshake method is called from the SSLSocket
    # constructor, there is no way to close it: we loose all
    # the references to the failed connection, except the
    # traceback.
    #
    # Using traceback (via sys.exc_info()) can lead to
    # unpredictable consequences with GC. So we have two more
    # choices:
    # 1. use monkey-patch for do_handshake()
    # 2. call it separately.
    #
    # The latter complicates the code by extra checks, that
    # will not be needed most of the time. So the monkey-patch
    # is cheaper.
    #
    ##
    try:
        self._sslobj.do_handshake()
    except Exception as e:
        self._sock.close()
        raise e


ssl.SSLSocket.do_handshake = _monkey_handshake


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
IPRCMD_RELOAD = 5
IPRCMD_ROUTE = 6


class netlink_error(socket.error):
    def __init__(self, code, msg=None):
        msg = msg or os.strerror(code)
        super(netlink_error, self).__init__(code, msg)
        self.code = code


class marshal(object):
    '''
    Generic marshalling class
    '''

    msg_map = {}

    def __init__(self):
        self.lock = threading.Lock()
        # one marshal instance can be used to parse one
        # message at once
        self.buf = None
        self.msg_map = self.msg_map or {}

    def set_buffer(self, init=b''):
        '''
        Set the buffer and return the data length
        '''
        self.buf = io.BytesIO()
        self.buf.write(init)
        self.buf.seek(0)
        return len(init)

    def parse(self, data):
        '''
        Parse the data in the buffer
        '''
        with self.lock:
            total = self.set_buffer(data)
            offset = 0
            result = []

            while offset < total:
                # pick type and length
                (length, msg_type) = struct.unpack('IH', self.buf.read(6))
                error = None
                if msg_type == NLMSG_ERROR:
                    self.buf.seek(16)
                    code = abs(struct.unpack('i', self.buf.read(4))[0])
                    if code > 0:
                        error = netlink_error(code)

                self.buf.seek(offset)
                msg_class = self.msg_map.get(msg_type, nlmsg)
                msg = msg_class(self.buf)
                msg.decode()
                msg['header']['error'] = error
                self.fix_message(msg)
                offset += msg.length
                result.append(msg)

            return result

    def fix_message(self, msg):
        pass


class netlink_socket(socket.socket):
    '''
    Generic netlink socket
    '''

    def __init__(self, family=NETLINK_GENERIC):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        self.pid = os.getpid()
        self.groups = None

    def bind(self, groups=0):
        self.groups = groups
        socket.socket.bind(self, (self.pid, self.groups))


class ssl_credentials(object):
    def __init__(self, key, cert, ca):
        self.key = key
        self.cert = cert
        self.ca = ca


class iothread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        # fd lists for select()
        self._rlist = set()
        self._wlist = set()
        self._xlist = set()
        self._stop = False
        # routing
        self.rtable = {}          # {client_socket: send_method, ...}
        self.families = {}        # {family_id: send_method, ...}
        self.marshals = {}        # {netlink_socket: marshal, ...}
        self.listeners = {}       # {int: Queue(), int: Queue()...}
        self.clients = set()      # set(socket, socket...)
        self.uplinks = set()      # set(socket, socket...)
        self.servers = set()      # set(socket, socket...)
        self.ssl_keys = {}        # {url: ssl_credentials(), url:...}
        self.mirror = False
        # control socket, for in-process communication only
        self.uuid = uuid.uuid4()
        self.control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.control.bind(b'\0%s' % (self.uuid))
        self._rlist.add(self.control)
        # debug
        self.record = False
        self.backlog = []

    def _get_socket(self, url, server_side):
        assert type(url) is str
        target = urlparse.urlparse(url)
        hostname = target.hostname or ''
        use_ssl = False
        ssl_version = 2

        if target.scheme[:4] == 'unix':
            if hostname and hostname[0] == '\0':
                address = hostname
            else:
                address = ''.join((hostname, target.path))
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            address = (socket.gethostbyname(hostname), target.port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if target.scheme.find('ssl') >= 0:
            ssl_version = ssl.PROTOCOL_SSLv3
            use_ssl = True

        if target.scheme.find('tls') >= 0:
            ssl_version = ssl.PROTOCOL_TLSv1
            use_ssl = True

        if use_ssl:
            if url not in self.ssl_keys:
                raise Exception('SSL/TLS keys are not provided')

            sock = ssl.wrap_socket(sock,
                                   keyfile=self.ssl_keys[url].key,
                                   certfile=self.ssl_keys[url].cert,
                                   ca_certs=self.ssl_keys[url].ca,
                                   server_side=server_side,
                                   cert_reqs=ssl.CERT_REQUIRED,
                                   ssl_version=ssl_version)
        return (sock, address)

    def distribute(self, data):
        """
        Send message to all clients. Called from self.route()
        """
        for sock in self.clients:
            sock.send(data)

    def route(self, sock, data):
        """
        Route message
        """
        # message type, offset 4 bytes, length 2 bytes
        mtype = struct.unpack('H', data[4:6])[0]
        # use NETLINK_UNUSED as inter-pyroute2
        # FIXME log routing failures
        if (mtype == NETLINK_UNUSED) and (sock in self.clients):
            #
            # Control messages
            #
            cmd = self.parse_control(data)
            if cmd['cmd'] == IPRCMD_ROUTE:
                #
                # Route request
                #
                family = cmd.get_attr('CTRL_ATTR_FAMILY_ID')[0]
                if family in self.families:
                    send = self.families[family]
                    self.rtable[sock] = send
                # TODO
                # * subscribe requests
                # * ...

        else:
            #
            # Data messages
            #
            if sock in self.rtable:
                send = self.rtable[sock]
                send(data)

    def parse_control(self, data):
        buf = io.BytesIO()
        buf.write(data)
        buf.seek(0)
        cmd = ctrlmsg(buf)
        cmd.decode()
        return cmd

    def parse(self, data, marshal):
        '''
        Parse and enqueue messages. A message can be
        retrieved from netlink socket as well as from a
        remote system, and it should be properly enqueued
        to make it available for netlink.get() method.

        If iothread.mirror is set, all messages will be also
        copied (mirrored) to the default 0 queue. Please
        make sure that 0 queue exists, before setting
        iothread.mirror to True.

        If there is no such queue for received
        sequence_number, leave sequence_number intact, but
        put the message into default 0 queue, if it exists.
        '''

        for msg in marshal.parse(data):
            if self.record:
                self.backlog.append((time.asctime(), msg))
            key = msg['header']['sequence_number']
            if key not in self.listeners:
                key = 0
            if self.mirror and key != 0:
                self.listeners[0].put(copy.deepcopy(msg))
            if key in self.listeners:
                self.listeners[key].put(msg)

    def command(self, cmd):
        msg = ctrlmsg(io.BytesIO())
        msg['header']['type'] = NETLINK_UNUSED
        msg['cmd'] = cmd
        msg.encode()
        return self.control.sendto(msg.buf.getvalue(),
                                   self.control.getsockname())

    def stop(self):
        return self.command(IPRCMD_STOP)

    def reload(self):
        return self.command(IPRCMD_RELOAD)

    def add_server(self, url):
        '''
        Add a server socket to listen for clients on
        '''
        (sock, address) = self._get_socket(url, server_side=False)
        sock.bind(address)
        sock.listen(16)
        self._rlist.add(sock)
        self.servers.add(sock)
        self.reload()
        return sock

    def remove_server(self, sock=None, address=None):
        assert sock or address
        if address:
            for sock in self.servers:
                if sock.getsockname() == address:
                    break
        assert sock
        self._rlist.remove(sock)
        self.servers.remove(sock)
        self.reload()
        return sock

    def add_uplink(self, url=None, family=None, groups=None):
        '''
        Add an uplink to get information from:

        * url -- remote serve
        * family and groups -- netlink
        '''
        if url is not None:
            (sock, address) = self._get_socket(url, server_side=False)
            sock.connect(address)
        elif (family is not None) and \
             (groups is not None):
            sock = netlink_socket(family)
            sock.bind(groups)
        else:
            raise Exception("uplink type not supported")
        self._rlist.add(sock)
        self.uplinks.add(sock)
        self.rtable[sock] = self.distribute
        self.reload()
        return sock

    def remove_uplink(self, sock):
        assert sock in self.uplinks
        self._rlist.remove(sock)
        self.uplinks.remove(sock)
        self.reload()
        return sock

    def add_client(self, sock):
        '''
        Add a client connection. Should not be called
        manually, but only on a client connect.
        '''
        self._rlist.add(sock)
        self._wlist.add(sock)
        self.clients.add(sock)
        self.reload()
        return sock

    def remove_client(self, sock):
        self._rlist.remove(sock)
        self._wlist.remove(sock)
        self.clients.remove(sock)
        return sock

    def run(self):
        while not self._stop:
            [rlist, wlist, xlist] = select.select(self._rlist, [], [])
            for fd in rlist:

                ##
                #
                # Incoming client connections
                #
                if fd in self.servers:
                    try:
                        (client, addr) = fd.accept()
                        self.add_client(client)
                    except ssl.SSLError:
                        # FIXME log SSL errors
                        pass
                    except:
                        traceback.print_exc()
                    continue

                ##
                #
                # Receive data from already open connection
                #
                # FIXME max length
                data = fd.recv(16384)
                if self.record:
                    self.backlog.append((time.asctime(), data))

                ##
                #
                # Control socket, only type == NETLINK_UNUSED
                #
                if fd == self.control:
                    # FIXME move it to specific marshal
                    cmd = self.parse_control(data)
                    if cmd['cmd'] == IPRCMD_STOP:
                        self._stop = True
                        break
                    elif cmd['cmd'] == IPRCMD_RELOAD:
                        pass

                ##
                #
                # Incoming packet from remote client
                #
                elif fd in self.clients:
                    if data == '':
                        # client closed connection
                        self.remove_client(fd)
                    else:
                        try:
                            self.route(fd, data)
                        except:
                            # drop packet on any error
                            traceback.print_exc()

                ##
                #
                # Incoming packet from uplink
                #
                elif fd in self.uplinks:
                    if data == '':
                        # uplink closed connection
                        self.remove_uplink(fd)
                    else:
                        self.route(fd, data)
                        try:
                            self.parse(data, self.marshals[fd])
                        except:
                            # drop packet on any error
                            pass


class netlink(object):
    '''
    Main netlink messaging class. It automatically spawns threads
    to monitor network and netlink I/O, creates and destroys message
    queues.

    It can operate in three modes:
     * local system only
     * server mode
     * client mode

    By default, it starts in local system only mode. To start a
    server, you should call netlink.serve(url). The method
    can be called several times to listen on specific interfaces
    and/or ports.

    Alternatively, you can start the object in the client mode.
    In that case you should provide server url in the host
    parameter. You can not mix server and client modes, so
    message proxy/relay not possible yet. This will be fixed
    in the future.

    Urls should be specified in the form:
        (host, port)

    E.g.:
        nl = netlink(host=('127.0.0.1', 7000))
    '''

    family = NETLINK_GENERIC
    groups = 0
    marshal = marshal

    def __init__(self, debug=False, host='localsystem', interruptible=False,
                 key=None, cert=None, ca=None):
        self.server = host
        self.iothread = iothread()
        self.listeners = self.iothread.listeners
        self.ssl_keys = self.iothread.ssl_keys
        self.interruptible = interruptible
        if key:
            self.ssl_keys[host] = ssl_credentials(key, cert, ca)
        if host == 'localsystem':
            self.socket = self.iothread.add_uplink(family=self.family,
                                                   groups=self.groups)
        else:
            self.socket = self.iothread.add_uplink(url=self.server)
            self.request_route()
        self.iothread.marshals[self.socket] = self.marshal()
        self.iothread.families[self.family] = self.send
        self.iothread.start()
        self.debug = debug
        self._nonce = 1
        self.servers = {}

    def request_route(self):
        rmsg = ctrlmsg()
        rmsg['header']['type'] = NETLINK_UNUSED
        rmsg['cmd'] = IPRCMD_ROUTE
        rmsg['attrs'] = (('CTRL_ATTR_FAMILY_ID', self.family), )
        rmsg.encode()
        self.socket.send(rmsg.buf.getvalue())

    def shutdown(self, url=None):
        url = url or self.servers.keys()[0]
        self.iothread.remove_server(self.servers[url])
        if url in self.ssl_keys:
            del self.ssl_keys[url]
        del self.servers[url]

    def serve(self, url, key=None, cert=None, ca=None):
        if key:
            self.ssl_keys[url] = ssl_credentials(key, cert, ca)
        self.servers[url] = self.iothread.add_server(url)

    def nonce(self):
        '''
        Increment netlink protocol nonce (there is no need to
        call it directly)
        '''
        if self._nonce == 0xffffffff:
            self._nonce = 1
        else:
            self._nonce += 1
        return self._nonce

    def mirror(self, operate=True):
        '''
        Turn message mirroring on/off. When it is 'on', all
        received messages will be copied (mirrored) into the
        default 0 queue.
        '''
        self.monitor(operate)
        self.iothread.mirror = operate

    def monitor(self, operate=True):
        '''
        Create/destroy the default 0 queue. Netlink socket
        receives messages all the time, and there are many
        messages that are not replies. They are just
        generated by the kernel as a reflection of settings
        changes. To start receiving these messages, call
        netlink.monitor(). They can be fetched by
        netlink.get(0) or just netlink.get().
        '''
        if operate:
            self.listeners[0] = Queue.Queue()
        else:
            del self.listeners[0]

    def get(self, key=0, interruptible=False):
        '''
        Get a message from a queue

        * key -- message queue number
        * interruptible -- catch ctrl-c

        Please note, that setting interruptible=True will cause
        polling overhead. Python starts implied poll cycle, if
        timeout is set.
        '''
        queue = self.listeners[key]
        interruptible = interruptible or self.interruptible
        if interruptible:
            tot = 31536000
        else:
            tot = None
        result = []
        while True:
            # timeout is set to catch ctrl-c
            # Bug-Url: http://bugs.python.org/issue1360
            msg = queue.get(block=True, timeout=tot)
            if msg['header']['error'] is not None:
                raise msg['header']['error']
            if msg['header']['type'] != NLMSG_DONE:
                result.append(msg)
            if (msg['header']['type'] == NLMSG_DONE) or \
               (not msg['header']['flags'] & NLM_F_MULTI):
                break
        # not default queue
        if key != 0:
            # delete the queue
            del self.listeners[key]
            # get remaining messages from the queue and
            # re-route them to queue 0 or drop
            while not queue.empty():
                msg = queue.get(bloc=True, timeout=tot)
                if 0 in self.listeners:
                    self.listeners[0].put(msg)
        return result

    def send(self, buf):
        '''
        Send a buffer or to the local kernel, or to
        the server, depending on the setup.
        '''
        if self.server == 'localsystem':
            self.socket.sendto(buf, (0, 0))
        else:
            self.socket.send(buf)

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST):
        '''
        Send netlink request, filling common message
        fields, and wait for response.
        '''
        # FIXME make it thread safe, yeah
        nonce = self.nonce()
        self.listeners[nonce] = Queue.Queue()
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg.encode()
        self.send(msg.buf.getvalue())
        result = self.get(nonce)
        if not self.debug:
            for i in result:
                del i['header']
        return result
