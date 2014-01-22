import os
import select
import traceback
import threading
try:
    import Queue
except ImportError:
    import queue as Queue


class IOLoop(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self, name="IOLoop")
        fd, self.control = os.pipe()
        self._stop = False
        self.fds = {}
        self.poll = select.epoll()
        self.register(fd, lambda fd, event: os.read(fd, 1))
        self.buffers = Queue.Queue()
        self._dequeue_thread = threading.Thread(target=self._dequeue,
                                                name='Buffers queue')

    def _dequeue(self):
        while True:
            cb, fd, data, argv, kwarg = self.buffers.get()

            if self._stop:
                break

            try:
                cb(fd, data, *argv, **kwarg)
            except:
                traceback.print_exc()

    def shutdown(self):
        self._stop = True
        self.reload()
        self.buffers.put((None, None, None, None, None))
        self._dequeue_thread.join()

    def reload(self):
        os.write(self.control, 's')

    def register(self, fd, cb, argv=[], kwarg={}, defer=False):
        if isinstance(fd, int):
            fdno = fd
        else:
            fdno = fd.fileno()
        assert fdno != self.control

        if defer:
            def wrap(fd, event, *argv, **kwarg):
                data = fd.recv(16384)
                self.buffers.put((cb, fd, data, argv, kwarg))
            self.fds[fdno] = [wrap, fd, argv, kwarg]
        else:
            self.fds[fdno] = [cb, fd, argv, kwarg]

        self.poll.register(fdno, select.EPOLLIN)
        self.reload()

    def unregister(self, fd):
        fdno = fd.fileno()
        assert fdno != self.control

        if fdno in self.fds:
            del self.fds[fdno]
            self.poll.unregister(fdno)
            self.reload()
            return True

        return False

    def run(self):
        self._dequeue_thread.start()
        while True:
            fds = self.poll.poll()

            if self._stop:
                break

            for (fdno, event) in fds:
                try:
                    rc = self.fds[fdno]
                    rc[0](rc[1], event, *rc[2], **rc[3])
                except KeyError:
                    pass
                except:
                    traceback.print_exc()
