import os
import socket
import select
import logging
import traceback
import threading
try:
    import Queue
except ImportError:
    import queue as Queue


class IOLoop(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self, name="IOLoop")
        self.fd, self.control = os.pipe()
        self._stop_flag = False
        self.fds = {}
        self.poll = select.epoll()
        self.register(self.fd, lambda f, event: os.read(f, 1))
        self.buffers = Queue.Queue()
        self._dequeue_thread = threading.Thread(target=self._dequeue,
                                                name='Buffers queue')
        self.setDaemon(True)
        self._dequeue_thread.setDaemon(True)

    def _dequeue(self):
        while True:
            cb, fd, data, argv, kwarg = self.buffers.get()

            if self._stop_flag:
                break

            try:
                cb(fd, data, *argv, **kwarg)
            except:
                logging.warning(traceback.format_exc())

    def shutdown(self):
        self._stop_flag = True
        self.reload()
        self.buffers.put((None, None, None, None, None))
        self._dequeue_thread.join()
        # wait the main loop to exit
        self.join()
        # close own file descriptors
        os.close(self.control)
        os.close(self.fd)
        self.poll.close()

    def reload(self):
        os.write(self.control, b's')

    def register(self, fd, cb, argv=[], kwarg={}, defer=False):
        if isinstance(fd, int):
            fdno = fd
        else:
            fdno = fd.fileno()
        assert fdno != self.control

        if defer:
            def wrap(fd, event, *argv, **kwarg):
                try:
                    data = fd.recv(16384)
                except OSError:
                    data = ''
                self.buffers.put((cb, fd, data, argv, kwarg))
            self.fds[fdno] = [wrap, fd, argv, kwarg]
        else:
            self.fds[fdno] = [cb, fd, argv, kwarg]

        self.poll.register(fdno, select.EPOLLIN)
        self.reload()

    def unregister(self, fd):
        try:
            fdno = fd.fileno()
        except socket.error:
            return False

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
            try:
                fds = self.poll.poll()
            except IOError:
                continue

            if self._stop_flag:
                break

            for (fdno, event) in fds:
                try:
                    rc = self.fds[fdno]
                    rc[0](rc[1], event, *rc[2], **rc[3])
                except KeyError:
                    pass
                except:
                    logging.warning(traceback.format_exc())
