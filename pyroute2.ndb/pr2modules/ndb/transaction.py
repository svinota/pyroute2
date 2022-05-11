import logging
import threading

log = logging.getLogger(__name__)


class Transaction(object):
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
