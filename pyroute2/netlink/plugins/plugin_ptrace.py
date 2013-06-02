'''
The code is based on python-ptrace's strace.py
'''
import io
import socket
import struct
import Queue
import threading
from pyroute2.common import Dotkeys

from ptrace.debugger import PtraceDebugger
from ptrace.debugger import Application
from ptrace.debugger import ProcessExit
from ptrace.debugger import ProcessSignal
from ptrace.debugger import NewProcessEvent
from ptrace.debugger import ProcessExecution

from ptrace.func_call import FunctionCallOptions


class SyscallTracer(Application):
    def __init__(self, command, marshal, no_stdout):
        Application.__init__(self)
        options = {'pid': None,
                   'fork': True,
                   'trace_exec': True,
                   'no_stdout': no_stdout,
                   'type': False,
                   'name': False,
                   'string_length': 256,
                   'raw_socketcall': False,
                   'address': False,
                   'array_count': 20,
                   'show_ip': False,
                   'enter': False}
        self.options = Dotkeys(options)
        self.program = command.split()
        self.marshal = marshal()
        self.queue = Queue.Queue()
        self.queue.persist = True
        self.processOptions()
        self.monitor = set()

    def syscall(self, process):
        state = process.syscall_state
        syscall = state.event(self.syscall_options)
        if syscall and (syscall.result is not None or self.options.enter):
            # register only AF_NETLINK sockets
            if syscall.name == 'socket':
                if syscall.arguments[0].value == socket.AF_NETLINK:
                    self.monitor.add(syscall.result)
            # deregister sockets
            elif syscall.name == 'close':
                if syscall.arguments[0].value in self.monitor:
                    self.monitor.remove(syscall.arguments[0].value)
            # get buffers
            elif syscall.name in ('recv',
                                  'recvmsg',
                                  'recvfrom',
                                  'send',
                                  'sendmsg',
                                  'sendto') and \
                    syscall.arguments[0].value in self.monitor:
                buf = io.BytesIO()
                # get buffer
                if syscall.name in ('recvmsg', 'sendmsg'):
# 8<------------------------------------------------------------
#
# man recv(2)
#
# struct msghdr {
#   void         *msg_name;       /* optional address */
#   socklen_t     msg_namelen;    /* size of address */
#   struct iovec *msg_iov;        /* scatter/gather array */
#   size_t        msg_iovlen;     /* # elements in msg_iov */
#   void         *msg_control;    /* ancillary data, see below */
#   size_t        msg_controllen; /* ancillary data buffer len */
#   int           msg_flags;      /* flags on received message */
# };
#
# struct iovec {                  /* Scatter/gather array items */
#   void  *iov_base;              /* Starting address */
#   size_t iov_len;               /* Number of bytes to transfer */
# };
#
                    # get msghdr
                    addr = syscall.arguments[1].value
                    # total length
                    total = syscall.result
                    # use P for size_t, hoping it will work on 32bit :)
                    mf = 'PIPPPPi'
                    ml = struct.calcsize(mf)
                    (msg_name,
                     msg_namelen,
                     msg_iov,
                     msg_iovlen,
                     msg_control,
                     msg_controllen,
                     msg_flags) = struct.unpack(mf,
                                                process.readBytes(addr, ml))
                    # iterate msg_iov
                    vf = 'PP'
                    vl = struct.calcsize(vf)
                    for i in range(msg_iovlen):
                        # next iov msg header
                        addr = msg_iov + vl * i
                        (iov_base,
                         iov_len) = struct.unpack(vf,
                                                  process.readBytes(addr, vl))
                        # read iov and store it in the buffer
                        length = min(total, iov_len)
                        buf.write(process.readBytes(iov_base, length))
                        total -= length
                        if total <= 0:
                            # FIXME: it should never be < 0
                            break
# 8<------------------------------------------------------------
                else:
                    # just read this damn buffer
                    addr = syscall.arguments[1].value
                    length = syscall.result
                    buf.write(process.readBytes(addr, length))
                for msg in self.marshal.parse(buf.getvalue()):
                    msg['header']['syscall'] = syscall.name
                    self.queue.put(msg)

        # Break at next syscall
        process.syscall()

    def prepareProcess(self, process):
        process.syscall()

    def newProcess(self, event):
        process = event.process
        self.prepareProcess(process)
        process.parent.syscall()

    def processExecution(self, event):
        process = event.process
        process.syscall()

    def runDebugger(self):
        # Create debugger and traced process
        self.setupDebugger()
        process = self.createProcess()
        if not process:
            return

        self.syscall_options = FunctionCallOptions(
            write_types=self.options.type,
            write_argname=self.options.name,
            string_max_length=self.options.string_length,
            replace_socketcall=not self.options.raw_socketcall,
            write_address=self.options.address,
            max_array_count=self.options.array_count,
        )
        self.syscall_options.instr_pointer = self.options.show_ip

        # First query to break at next syscall
        self.prepareProcess(process)

        while True:
            # No more process? Exit
            if not self.debugger:
                break

            # Wait until next syscall enter
            try:
                event = self.debugger.waitSyscall()
                process = event.process
            except ProcessExit, event:
                continue
            except ProcessSignal, event:
                process.syscall(event.signum)
                continue
            except NewProcessEvent, event:
                self.newProcess(event)
                continue
            except ProcessExecution, event:
                self.processExecution(event)
                continue

            # Process syscall enter or exit
            self.syscall(process)

    def main(self):
        self.debugger = PtraceDebugger()
        try:
            self.runDebugger()
        except ProcessExit:
            pass
        except Exception:
            import traceback
            traceback.print_exc()
        self.debugger.quit()
        self.queue.put(None)


def _create(command, marshal, **kwarg):
    #
    tracer = SyscallTracer(command, marshal, kwarg.get('no_stdout', False))
    thread = threading.Thread(target=tracer.main)
    thread.start()
    return tracer.queue


plugin_init = {'create': _create,
               'type': 'queue'}
