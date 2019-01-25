import os
import atexit
import pickle
import select
import struct
import logging
import signal
import threading
import traceback
from io import BytesIO
from socket import SOL_SOCKET
from socket import SO_RCVBUF
from pyroute2 import config
from pyroute2.netlink.nlsocket import NetlinkMixin
if config.uname[0][-3:] == 'BSD':
    from pyroute2.iproute.bsd import IPRoute
else:
    from pyroute2.iproute.linux import IPRoute
try:
    import queue
except ImportError:
    import Queue as queue

log = logging.getLogger(__name__)


class Transport(object):
    '''
    A simple transport protocols to send objects between two
    end-points. Requires an open file-like object at init.
    '''
    def __init__(self, file_obj):
        self.file_obj = file_obj
        self.lock = threading.Lock()
        self.cmd_queue = queue.Queue()
        self.brd_queue = queue.Queue()
        self.run = True

    def fileno(self):
        return self.file_obj.fileno()

    def send(self, obj):
        dump = BytesIO()
        pickle.dump(obj, dump)
        packet = struct.pack("II", len(dump.getvalue()) + 8, 0)
        packet += dump.getvalue()
        self.file_obj.write(packet)
        self.file_obj.flush()

    def __recv(self):
        length, offset = struct.unpack("II", self.file_obj.read(8))
        dump = BytesIO()
        dump.write(self.file_obj.read(length - 8))
        dump.seek(0)
        ret = pickle.load(dump)
        return ret

    def recv(self):
        while self.run:
            with self.lock:
                if not self.brd_queue.empty():
                    return self.brd_queue.get()
                try:
                    ret = self.__recv()
                except struct.error:
                    try:
                        return self.brd_queue.get(timeout=5)
                    except queue.Empty:
                        raise Exception('I/O error')
                if ret['stage'] == 'broadcast':
                    return ret
                self.cmd_queue.put(ret)

    def recv_cmd(self):
        while self.run:
            with self.lock:
                if not self.cmd_queue.empty():
                    return self.cmd_queue.get()
                ret = self.__recv()
                if ret['stage'] != 'broadcast':
                    return ret
                self.brd_queue.put(ret)

    def close(self):
        self.run = False


class ProxyChannel(object):

    def __init__(self, channel, stage):
        self.target = channel
        self.stage = stage

    def send(self, data):
        return self.target.send({'stage': self.stage,
                                 'data': data,
                                 'error': None})


def Server(trnsp_in, trnsp_out):

    def stop_server(signum, frame):
        Server.run = False

    Server.run = True
    signal.signal(signal.SIGTERM, stop_server)

    try:
        ipr = IPRoute()
        lock = ipr._sproxy.lock
        ipr._s_channel = ProxyChannel(trnsp_out, 'broadcast')
    except Exception as e:
        trnsp_out.send({'stage': 'init',
                        'error': e})
        return 255

    inputs = [ipr.fileno(), trnsp_in.fileno()]
    broadcasts = {ipr.fileno(): ipr}
    outputs = []

    # all is OK so far
    trnsp_out.send({'stage': 'init',
                    'uname': config.uname,
                    'error': None})

    # 8<-------------------------------------------------------------
    while Server.run:
        try:
            events, _, _ = select.select(inputs, outputs, inputs)
        except:
            continue
        for fd in events:
            if fd in broadcasts:
                sock = broadcasts[fd]
                bufsize = sock.getsockopt(SOL_SOCKET, SO_RCVBUF) // 2
                with lock:
                    error = None
                    data = None
                    try:
                        data = sock.recv(bufsize)
                    except Exception as e:
                        error = e
                        error.tb = traceback.format_exc()
                    trnsp_out.send({'stage': 'broadcast',
                                    'data': data,
                                    'error': error})
            elif fd == trnsp_in.fileno():
                cmd = trnsp_in.recv_cmd()
                if cmd['stage'] == 'shutdown':
                    ipr.close()
                    data = struct.pack('IHHQIQQ', 28, 2, 0, 0, 104, 0, 0)
                    trnsp_out.send({'stage': 'broadcast',
                                    'data': data,
                                    'error': None})
                    return
                elif cmd['stage'] == 'reconstruct':
                    error = None
                    try:
                        msg = cmd['argv'][0]()
                        msg.load(pickle.loads(cmd['argv'][1]))
                        ipr.sendto_gate(msg, cmd['argv'][2])
                    except Exception as e:
                        error = e
                        error.tb = traceback.format_exc()
                    trnsp_out.send({'stage': 'reconstruct',
                                    'error': error,
                                    'return': None,
                                    'cookie': cmd['cookie']})

                elif cmd['stage'] == 'command':
                    error = None
                    try:
                        ret = getattr(ipr, cmd['name'])(*cmd['argv'],
                                                        **cmd['kwarg'])
                        if cmd['name'] == 'bind' and \
                                ipr._brd_socket is not None:
                            inputs.append(ipr._brd_socket.fileno())
                            broadcasts[ipr._brd_socket.fileno()] = \
                                ipr._brd_socket
                    except Exception as e:
                        ret = None
                        error = e
                        error.tb = traceback.format_exc()
                    trnsp_out.send({'stage': 'command',
                                    'error': error,
                                    'return': ret,
                                    'cookie': cmd['cookie']})


class RemoteSocket(NetlinkMixin):

    trnsp_in = None
    trnsp_out = None
    remote_trnsp_in = None
    remote_trnsp_out = None

    def __init__(self, trnsp_in, trnsp_out):
        super(RemoteSocket, self).__init__()
        self.trnsp_in = trnsp_in
        self.trnsp_out = trnsp_out
        self.cmdlock = threading.Lock()
        self.shutdown_lock = threading.RLock()
        self.closed = False
        init = self.trnsp_in.recv_cmd()
        if init['stage'] != 'init':
            raise TypeError('incorrect protocol init')
        if init['error'] is not None:
            raise init['error']
        else:
            self.uname = init['uname']
            atexit.register(self.close)
        self.sendto_gate = self._gate

    def _gate(self, msg, addr):
        with self.cmdlock:
            self.trnsp_out.send({'stage': 'reconstruct',
                                 'cookie': None,
                                 'name': None,
                                 'argv': [type(msg),
                                          pickle.dumps(msg.dump()),
                                          addr],
                                 'kwarg': None})
            ret = self.trnsp_in.recv_cmd()
            if ret['error'] is not None:
                raise ret['error']
            return ret['return']

    def recv(self, bufsize, flags=0):
        msg = None
        while True:
            msg = self.trnsp_in.recv()
            if msg['stage'] == 'signal':
                os.kill(os.getpid(), msg['data'])
            else:
                break
        if msg['error'] is not None:
            raise msg['error']
        return msg['data']

    def _cleanup_atexit(self):
        if hasattr(atexit, 'unregister'):
            atexit.unregister(self.close)
        else:
            try:
                atexit._exithandlers.remove((self.close, (), {}))
            except ValueError:
                pass

    def close(self):
        with self.shutdown_lock:
            if not self.closed:
                super(RemoteSocket, self).close()
                self.closed = True
                self._cleanup_atexit()
                self.trnsp_out.send({'stage': 'shutdown'})
                # send loopback nlmsg to terminate possible .get()
                if self.remote_trnsp_out is not None:
                    data = struct.pack('IHHQIQQ', 28, 2, 0, 0, 104, 0, 0)
                    self.remote_trnsp_out.send({'stage': 'broadcast',
                                                'data': data,
                                                'error': None})
                    with self.trnsp_in.lock:
                        pass

                transport_objs = (self.trnsp_out, self.trnsp_in,
                                  self.remote_trnsp_in, self.remote_trnsp_out)

                # Stop the transport objects.
                for trnsp in transport_objs:
                    try:
                        if hasattr(trnsp, 'close'):
                            trnsp.close()
                    except Exception:
                        pass

                # Close the file descriptors.
                for trnsp in transport_objs:
                    try:
                        trnsp.file_obj.close()
                    except Exception:
                        pass

    def proxy(self, cmd, *argv, **kwarg):
        with self.cmdlock:
            self.trnsp_out.send({'stage': 'command',
                                 'cookie': None,
                                 'name': cmd,
                                 'argv': argv,
                                 'kwarg': kwarg})
            ret = self.trnsp_in.recv_cmd()
            if ret['error'] is not None:
                raise ret['error']
            return ret['return']

    def fileno(self):
        return self.trnsp_in.fileno()

    def bind(self, *argv, **kwarg):
        if 'async' in kwarg:
            # FIXME
            # raise deprecation error after 0.5.3
            #
            log.warning('use "async_cache" instead of "async", '
                        '"async" is a keyword from Python 3.7')
            del kwarg['async']
        # do not work with async servers
        kwarg['async_cache'] = False
        return self.proxy('bind', *argv, **kwarg)

    def send(self, *argv, **kwarg):
        return self.proxy('send', *argv, **kwarg)

    def sendto(self, *argv, **kwarg):
        return self.proxy('sendto', *argv, **kwarg)

    def getsockopt(self, *argv, **kwarg):
        return self.proxy('getsockopt', *argv, **kwarg)

    def setsockopt(self, *argv, **kwarg):
        return self.proxy('setsockopt', *argv, **kwarg)

    def _sendto(self, *argv, **kwarg):
        return self.sendto(*argv, **kwarg)

    def _recv(self, *argv, **kwarg):
        return self.recv(*argv, **kwarg)
