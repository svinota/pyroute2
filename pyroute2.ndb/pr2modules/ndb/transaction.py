import shlex
import shutil
import logging
import threading
import subprocess

global_log = logging.getLogger(__name__)


class CheckProcessException(Exception):
    pass


class CheckProcess:
    def __init__(self, command, log=None, timeout=None):
        if not isinstance(command, str):
            raise TypeError('command must be a non empty string')
        if not len(command) > 0:
            raise TypeError('command must be a non empty string')
        self.log = log or global_log
        self.command = command
        self.args = shlex.split(command)
        self.timeout = timeout
        self.return_code = None

    def commit(self):
        self.args[0] = shutil.which(self.args[0])
        if self.args[0] is None:
            raise FileNotFoundError()
        process = subprocess.Popen(
            self.args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            self.log.debug(f'process check {self.args}')
            out, err = process.communicate(timeout=self.timeout)
            self.log.debug(f'process output: {out}')
            self.log.debug(f'process stderr: {err}')
        except subprocess.TimeoutExpired:
            self.log.debug('process timeout expired')
            process.terminate()
            process.stdout.close()
            process.stderr.close()
        finally:
            self.return_code = process.wait()
        if self.return_code != 0:
            raise CheckProcessException('CheckProcess failed')

    def rollback(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        pass


class PingAddress(CheckProcess):
    def __init__(self, address, log=None, timeout=1):
        super(PingAddress, self).__init__(
            f'ping -c 1 -W {timeout} {address}', log=log
        )


class Transaction:
    def __init__(self, log):
        self.queue = []
        self.event = threading.Event()
        self.event.clear()
        self.log = log.channel('transaction.%s' % id(self))
        self.log.debug('begin transaction')

    def push(self, *argv):
        for obj in argv:
            self.log.debug('queue %s' % type(obj))
            self.queue.append(obj)
        return self

    def append(self, obj):
        self.log.debug('queue %s' % type(obj))
        self.push(obj)
        return self

    def pop(self, index=-1):
        self.log.debug('pop %s' % index)
        self.queue.pop(index)
        return self

    def insert(self, index, obj):
        self.log.debug('insert %i %s' % (index, type(obj)))
        self.queue.insert(index, obj)
        return self

    def cancel(self):
        self.log.debug('cancel transaction')
        self.queue = []
        return self

    def wait(self):
        return self.event.wait()

    def done(self):
        return self.event.is_set()

    def commit(self):
        self.log.debug('commit')
        rollbacks = []
        for obj in self.queue:
            rollbacks.append(obj)
            try:
                obj.commit()
            except Exception:
                for rb in reversed(rollbacks):
                    try:
                        rb.rollback()
                    except Exception as e:
                        self.log.warning('ignore rollback exception: %s' % e)
                raise
        self.event.set()
        return self
