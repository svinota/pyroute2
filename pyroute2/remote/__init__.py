import os
import atexit
import pickle
import select
import struct
import logging
import threading
import traceback
from io import BytesIO
from socket import SOL_SOCKET
from socket import SO_RCVBUF
from pyroute2 import IPRoute
from pyroute2.netlink.nlsocket import NetlinkMixin
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
        with self.lock:
            if not self.brd_queue.empty():
                return self.brd_queue.get()

            while True:
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
        with self.lock:
            if not self.cmd_queue.empty():
                return self.cmd_queue.get()

            while True:
                ret = self.__recv()
                if ret['stage'] != 'broadcast':
                    return ret
                self.brd_queue.put(ret)

    def close(self):
        self.file_obj.close()


class ProxyChannel(object):

    def __init__(self, channel, stage):
        self.target = channel
        self.stage = stage

    def send(self, data):
        return self.target.send({'stage': self.stage,
                                 'data': data,
                                 'error': None})


def Server(trnsp_in, trnsp_out):

    try:
        ipr = IPRoute()
        lock = ipr._sproxy.lock
        ipr._s_channel = ProxyChannel(trnsp_out, 'broadcast')
    except Exception as e:
        trnsp_out.send({'stage': 'init',
                        'error': e})
        return 255

    inputs = [ipr.fileno(), trnsp_in.fileno()]
    outputs = []

    # all is OK so far
    trnsp_out.send({'stage': 'init',
                    'error': None})

    # 8<-------------------------------------------------------------
    while True:
        try:
            events, _, _ = select.select(inputs, outputs, inputs)
        except:
            continue
        for fd in events:
            if fd == ipr.fileno():
                bufsize = ipr.getsockopt(SOL_SOCKET, SO_RCVBUF) // 2
                with lock:
                    error = None
                    data = None
                    try:
                        data = ipr.recv(bufsize)
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
                    return
                elif cmd['stage'] == 'reconstruct':
                    error = None
                    try:
                        msg = cmd['argv'][0]()
                        msg.load(pickle.loads(cmd['argv'][1]))
                        msg.encode()
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
                    except Exception as e:
                        ret = None
                        error = e
                        error.tb = traceback.format_exc()
                    trnsp_out.send({'stage': 'command',
                                    'error': error,
                                    'return': ret,
                                    'cookie': cmd['cookie']})


class Client(object):

    trnsp_in = None
    trnsp_out = None

    def __init__(self):
        self.cmdlock = threading.Lock()
        self.shutdown_lock = threading.Lock()
        self.closed = False
        init = self.trnsp_in.recv_cmd()
        if init['stage'] != 'init':
            raise TypeError('incorrect protocol init')
        if init['error'] is not None:
            raise init['error']
        else:
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
                self.closed = True
                self._cleanup_atexit()
                self.trnsp_out.send({'stage': 'shutdown'})
                # send loopback nlmsg to terminate possible .get()
                data = struct.pack('IHHQIQQ', 28, 2, 0, 0, 104, 0, 0)
                self.remote_trnsp_out.send({'stage': 'broadcast',
                                            'data': data,
                                            'error': None})
                with self.trnsp_in.lock:
                    pass
                for trnsp in (self.trnsp_out,
                              self.trnsp_in,
                              self.remote_trnsp_in,
                              self.remote_trnsp_out):
                    try:
                        if hasattr(trnsp, 'close'):
                            trnsp.close()
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


class RemoteSocket(NetlinkMixin, Client):

    def bind(self, *argv, **kwarg):
        return Client.bind(self, *argv, **kwarg)

    def close(self):
        NetlinkMixin.close(self)
        Client.close(self)

    def _sendto(self, *argv, **kwarg):
        return Client.sendto(self, *argv, **kwarg)

    def _recv(self, *argv, **kwarg):
        return Client.recv(self, *argv, **kwarg)
