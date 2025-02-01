import builtins
import gc
import json
import logging
import multiprocessing
import os
import select
import signal
import socket
from collections import namedtuple

from pyroute2 import config
from pyroute2.netlink import exceptions as pyroute2_exceptions

log = logging.getLogger(__name__)


def wrapper(ctrl, func, argv):
    gc.disable()
    payload = {}
    fds = []
    sockets = []
    try:
        ret = func(*argv)
        if isinstance(ret, ChildProcessReturnValue):
            ret, sockets = ret
        if ret is not None:
            payload = {'data': ret}
        if sockets:
            fds = [x.fileno() for x in sockets]
    except Exception as e:
        payload = {'exception': e.__class__.__name__, 'options': e.args}
        fds = []
    finally:
        socket.send_fds(
            ctrl, [json.dumps(payload).encode('utf-8')], fds, len(fds)
        )


ChildProcessReturnValue = namedtuple(
    'ChildProcessReturnValue', ('payload', 'fds')
)


class ChildProcess:
    def __init__(self, target, args):
        self.ctrl_r, self.ctrl_w = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_DGRAM
        )
        self._mode = config.child_process_mode
        self._target = target
        self._args = args
        self._proc = None
        self._running = False

    def close(self):
        self.ctrl_r.close()
        self.ctrl_w.close()
        self.stop()

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def mode(self):
        return self._mode

    def communicate(self, timeout=1):
        rl, _, _ = select.select([self.ctrl_r], [], [], 400)
        if not len(rl):
            self.stop(kill=True, reason='no response from child')
            return None

        (data, fds, _, _) = socket.recv_fds(self.ctrl_r, 1024, 1)
        payload = json.loads(data.decode('utf-8'))
        if payload:
            if set(payload.keys()) != set(('exception', 'options')):
                raise TypeError('error loading child feedback')
            if payload['exception'] is not None:
                error_class = getattr(builtins, payload['exception'], None)
                if error_class is None:
                    error_class = getattr(
                        pyroute2_exceptions, payload['exception'], None
                    )
                if error_class is None:
                    error_class = Exception
                if not issubclass(error_class, Exception):
                    raise TypeError('error loading child error')
                raise error_class(*payload['options'])
        return fds

    @property
    def proc(self):
        if self._proc is None:
            raise RuntimeError('not started')
        return self._proc

    @proc.setter
    def proc(self, value):
        self._proc = value

    def _unsupported(self):
        raise TypeError('unsupported mode')

    def run(self):
        if self._running:
            return
        self._running = True
        if self.mode == 'fork':
            self.pid = os.fork()
            if self.pid == 0:
                wrapper(self.ctrl_w, self._target, self._args)
                os._exit(0)
        elif self.mode == 'mp':
            self.proc = multiprocessing.Process(
                target=wrapper, args=[self.ctrl_w, self._target, self._args]
            )
            self.proc.start()
        else:
            self._unsupported()

    def stop(self, kill=False, reason=None):
        if not self._running:
            return
        self._running = False
        if self.mode == 'fork':
            if kill:
                os.kill(self.pid, signal.SIGKILL)
            else:
                os.kill(self.pid, signal.SIGTERM)
            os.waitpid(self.pid, 0)
        elif self.mode == 'mp':
            if kill:
                self.proc.kill()
            else:
                self.proc.terminate()
            self.proc.join()
        else:
            self._unsupported()
        if reason is not None:
            log.warning(reason)

    @property
    def exitcode(self):
        if self.mode == 'fork':
            return self._exitcode
        elif self.mode == 'mp':
            return self.proc.exitcode
        else:
            self._unsupported()
