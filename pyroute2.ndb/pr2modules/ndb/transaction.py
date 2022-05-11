'''

General description.

One object
----------

All the changes done via one object are applied
in the order defined by the corresponding class.

.. code-block:: python

    eth0 = ndb.interfaces["eth0"]
    eth0.add_ip(address="10.0.0.1", prefixlen=24)
    eth0.set(state="up")
    eth0.commit()

In the example above first the interface
attributes like state, mtu, ifname etc. will be
applied, and only then IP addresses, bridge ports
and like that, despite the order they are written
before `commit()` call.

The order is ok for most of cases. But if not,
one can control it by calling `commit()` in the
required places, breaking one transaction into
several sequential transactions.

And since RTNL object methods return itself, it
is possible to write chains with multiple
`commit()`:

.. code-block:: python

    (
        ndb.interfaces
        .create(ifname="test", kind="dummy")
        .add_ip(address="10.0.0.1", prefixlen=24)
        .commit()
        .set(state="up")
        .commit()
    )

Here the order is forced by explicit commits.

Multiple objects
----------------

An important functionality of NDB are rollbacks.
And there is a way to batch changes on multiple
objects so one failure will trigger rollback of
all the changes on all the objects.

.. code-block:: python

    ctx = ndb.begin()
    ctx.push(
        (
            ndb.interfaces
            .create(ifname="br0", kind="bridge")
            .add_port("eth0")
            .add_port("eth1")
            .set(state="up")
            .add_ip("10.0.0.2/24")
        ),
        (
            ndb.routes
            .create(
                dst="192.168.0.0",
                dst_len=24,
                gateway="10.0.0.1"
            )
        )
    )
    ctx.commit()


Check external processes
------------------------

The simplest usecase for external checks is to
test if a remote IP is still reachable after
the changes are applied:


.. code-block:: python

    from pyroute2.ndb.transaction import PingAddress

    ctx = ndb.begin()
    ctx.push(
        ndb.routes.create(
          dst="10.0.0.0",
          dst_len=24,
          gateway="172.16.0.1"
        ),
        PingAddress("10.0.0.1")
    )
'''
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
