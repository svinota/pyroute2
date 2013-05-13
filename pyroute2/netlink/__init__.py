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


def _repr_sockets(sockets, mode):
    '''
    Represent socket as a text string
    '''
    ret = []
    for i in sockets:
        url = ''
        if i.family == socket.AF_UNIX:
            url = 'unix'
        if type(i) == ssl.SSLSocket:
            if url:
                url += '+'
            if i.ssl_version == ssl.PROTOCOL_SSLv3:
                url += 'ssl'
            elif i.ssl_version == ssl.PROTOCOL_TLSv1:
                url += 'tls'
        if not url:
            url = 'tcp'
        if i.family == socket.AF_UNIX:
            url += '://%s' % (i.getsockname())
        else:
            if mode == 'local':
                url += '://%s:%i' % (i.getsockname())
            elif mode == 'remote':
                url += '://%s:%i' % (i.getpeername())
        ret.append(url)
    return ret


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


class masq_record(object):
    def __init__(self, seq, pid, socket):
        self.seq = seq
        self.pid = pid
        self.socket = socket
        self.ctime = time.time()

    def __repr__(self):
        return "%s, %s, %s, %s" % (_repr_sockets([self.socket], 'remote'),
                                   self.pid, self.seq, time.ctime(self.ctime))


class iothread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.pid = os.getpid()
        self._nonce = 0
        self._stop = False
        self._reload_event = threading.Event()
        # fd lists for select()
        self._rlist = set()
        self._wlist = set()
        self._xlist = set()
        # routing
        self.rtable = {}          # {client_socket: send_method, ...}
        self.families = {}        # {family_id: send_method, ...}
        self.marshals = {}        # {netlink_socket: marshal, ...}
        self.listeners = {}       # {int: Queue(), int: Queue()...}
        self.masquerade = {}      # {int: masq_record()...}
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
        # masquerade cache expiration
        self._expire_thread = threading.Thread(target=self._expire_masq)
        self._expire_thread.setDaemon(True)
        self._expire_thread.start()
        # buffers reassembling
        self.buffers = Queue.Queue()
        self._feed_thread = threading.Thread(target=self._feed_buffers)
        self._feed_thread.setDaemon(True)
        self._feed_thread.start()
        # debug
        self.record = False
        self.backlog = []

    def _feed_buffers(self):
        '''
        Beckground thread to feed reassembled buffers to the parser
        '''
        save = None
        while not self._stop:
            (buf, marshal) = self.buffers.get()
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
                length = struct.unpack('I', buf.read(4))[0]
                if offset + length > buf.length:
                    # create save buffer
                    buf.seek(offset)
                    save = io.BytesIO()
                    save.length = save.write(buf.read())
                    # truncate the buffer
                    buf.truncate(offset)
                    break
                offset += length
            # feed buffer to the parser
            try:
                self.parse(buf.getvalue(), marshal)
            except:
                traceback.print_exc()

    def _expire_masq(self):
        '''
        Background thread that expires masquerade cache entries
        '''
        while not self._stop:
            # expire masquerade records
            ts = time.time()
            for i in tuple(self.masquerade.keys()):
                if (ts - self.masquerade[i].ctime) > 60:
                    del self.masquerade[i]
            time.sleep(60)

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

    def nonce(self):
        if self._nonce == 0xffffffff:
            self._nonce = 1
        else:
            self._nonce += 1
        return self._nonce

    def distribute(self, data):
        """
        Send message to all clients. Called from self.route()
        """
        data.seek(8)
        # read sequence number and pid
        seq, pid = struct.unpack('II', data.read(8))
        # default target -- broadcast
        target = None
        # if it is a unicast response
        if pid == self.pid:
            # lookup masquerade table
            target = self.masquerade.get(seq, None)
        # there is valid masquerade record
        if target is not None:
            # fill up client's pid and seq
            offset = 0
            # ... but -- for each message in the packet :)
            while offset < data.length:
                # write the data
                data.seek(offset + 8)
                data.write(struct.pack('II', target.seq, target.pid))
                # skip to the next message
                data.seek(offset)
                length = struct.unpack('I', data.read(4))[0]
                offset += length

            target.socket.send(data.getvalue())
        else:
            # otherwise, broadcast packet
            for sock in self.clients:
                sock.send(data.getvalue())
            # return True -- this packet should be parsed
            return True

    def route(self, sock, data):
        """
        Route message
        """
        data.seek(4)
        # message type, offset 4 bytes, length 2 bytes
        mtype = struct.unpack('H', data.read(2))[0]
        # FIXME log routing failures

        ##
        #
        # NETLINK_UNUSED as inter-pyroute2
        #
        if (mtype == NETLINK_UNUSED) and (sock in self.clients):
            cmd = self.parse_control(data)
            if cmd['cmd'] == IPRCMD_ROUTE:
                # routing request
                family = cmd.get_attr('CTRL_ATTR_FAMILY_ID')[0]
                if family in self.families:
                    send = self.families[family]
                    self.rtable[sock] = send
                # TODO
                # * subscribe requests
                # * ...

        ##
        #
        # NETLINK_UNUSED as intra-pyroute2
        #
        elif (mtype == NETLINK_UNUSED) and (sock == self.control):
            cmd = self.parse_control(data)
            if cmd['cmd'] == IPRCMD_STOP:
                # Stop iothread
                self._stop = True
            elif cmd['cmd'] == IPRCMD_RELOAD:
                # Reload io cycle
                self._reload_event.set()

        ##
        #
        # Data messages
        #
        else:
            if sock in self.clients:
                # create masquerade record for client's messages
                # 1. generate nonce
                nonce = self.nonce()
                # 2. save masquerade record, invalidating old one
                data.seek(8)
                seq, pid = struct.unpack('II', data.read(8))
                self.masquerade[nonce] = masq_record(seq, pid, sock)
                # 3. overwrite seq and pid
                data.seek(8)
                data.write(struct.pack('II', nonce, self.pid))

            if sock in self.rtable:
                if self.rtable[sock](data):
                    self.buffers.put((data, self.marshals[sock]))

    def parse_control(self, data):
        data.seek(0)
        cmd = ctrlmsg(data)
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
        '''
        Reload I/O cycle. Warning: this method should be never
        called from iothread, as it will not return.
        '''
        self._reload_event.clear()
        ret = self.command(IPRCMD_RELOAD)
        self._reload_event.wait()
        return ret

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
                data = io.BytesIO()
                data.length = data.write(fd.recv(16384))

                ##
                #
                # Close socket
                #
                if data.length == 0:
                    if fd in self.clients:
                        self.remove_client(fd)
                    elif fd in self.uplinks:
                        self.remove_uplink(fd)
                    continue

                ##
                #
                # Route the data
                #
                if self.record:
                    self.backlog.append((time.asctime(),
                                         fd.getsockname(),
                                         data))
                self.route(fd, data)


class netlink(object):
    '''
    Main netlink messaging class. It automatically spawns threads
    to monitor network and netlink I/O, creates and destroys message
    queues.

    By default, netlink class connects to the local netlink socket
    on startup. If you prefer to connect to another host, use::

        nl = netlink(host='tcp://remote.01host:7000')

    It is possible to connect to uplinks after the startup::

        nl = netlink(do_connect=False)
        nl.connect('tcp://remote.01host:7000')

    To act as a server, call serve()::

        nl = netlink(do_connect=False)
        nl.connect('localsystem')
        nl.serve('unix:///tmp/pyroute')
    '''

    family = NETLINK_GENERIC
    groups = 0
    marshal = marshal

    def __init__(self, debug=False, interruptible=False, do_connect=True,
                 host='localsystem', key=None, cert=None, ca=None):
        self.iothread = iothread()
        self.listeners = self.iothread.listeners
        self.ssl_keys = self.iothread.ssl_keys
        self.interruptible = interruptible
        self.sockets = set()
        self.servers = {}
        self.iothread.families[self.family] = self.send
        self.iothread.start()
        self.debug = debug
        if do_connect:
            self.connect(host, key, cert, ca)

    def connect(self, host='localsystem', key=None, cert=None, ca=None):
        if key:
            self.ssl_keys[host] = ssl_credentials(key, cert, ca)
        if host == 'localsystem':
            sock = self.iothread.add_uplink(family=self.family,
                                            groups=self.groups)
        else:
            sock = self.iothread.add_uplink(url=host)
            smsg = ctrlmsg()
            smsg['header']['type'] = NETLINK_UNUSED
            smsg['header']['pid'] = os.getpid()
            smsg['cmd'] = IPRCMD_ROUTE
            smsg['attrs'] = (('CTRL_ATTR_FAMILY_ID', self.family), )
            smsg.encode()
            sock.send(smsg.buf.getvalue())
        self.iothread.marshals[sock] = self.marshal()
        self.sockets.add(sock)

    def shutdown(self, url=None):
        url = url or self.servers.keys()[0]
        self.iothread.remove_server(self.servers[url])
        if url in self.ssl_keys:
            del self.ssl_keys[url]
        del self.servers[url]

    def get_servers(self):
        return _repr_sockets(self.iothread.servers, 'local')

    def get_clients(self):
        return _repr_sockets(self.iothread.clients, 'remote')

    def serve(self, url, key=None, cert=None, ca=None):
        if key:
            self.ssl_keys[url] = ssl_credentials(key, cert, ca)
        self.servers[url] = self.iothread.add_server(url)

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
        data = buf.getvalue()
        for sock in self.sockets:
            if isinstance(sock, netlink_socket):
                sock.sendto(data, (0, 0))
            else:
                sock.send(data)

    def nlm_request(self, msg, msg_type,
                    msg_flags=NLM_F_DUMP | NLM_F_REQUEST):
        '''
        Send netlink request, filling common message
        fields, and wait for response.
        '''
        # FIXME make it thread safe, yeah
        nonce = self.iothread.nonce()
        self.listeners[nonce] = Queue.Queue()
        msg['header']['sequence_number'] = nonce
        msg['header']['pid'] = os.getpid()
        msg['header']['type'] = msg_type
        msg['header']['flags'] = msg_flags
        msg.encode()
        self.send(msg.buf)
        result = self.get(nonce)
        if not self.debug:
            for i in result:
                del i['header']
        return result
