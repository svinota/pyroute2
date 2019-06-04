
import os
import socket
import ctypes
import ctypes.util
import threading
from pyroute2.inotify.inotify_msg import inotify_msg


class Inotify(object):

    def __init__(self, libc=None, path=None):
        self.fd = None
        self.wd = {}
        self.path = set(path)
        self.lock = threading.RLock()
        self.libc = libc or ctypes.CDLL(ctypes.util.find_library('c'),
                                        use_errno=True)

    def bind(self, *argv, **kwarg):
        with self.lock:
            if self.fd is not None:
                raise socket.error(22, 'Invalid argument')
            self.fd = self.libc.inotify_init()
            for path in self.path:
                self.register_path(path)

    def register_path(self, path, mask=0x100 | 0x200):
        os.stat(path)
        with self.lock:
            if path in self.wd:
                return
            if self.fd is not None:
                wd = (self
                      .libc
                      .inotify_add_watch(self.fd, path, mask))
                self.wd[wd] = path
            self.path.add(path)

    def unregister_path(self):
        pass

    def get(self):
        # get the reader
        return self.parse(os.read(self.fd, 4096))

    def close(self):
        os.close(self.fd)

    def parse(self, data):

        offset = 0

        while offset <= len(data) - 16:
            # pick one header
            msg = inotify_msg(data, offset=offset)
            msg.decode()
            if msg['wd'] == 0:
                break
            msg['path'] = self.wd[msg['wd']]
            offset += msg.length
            yield msg
