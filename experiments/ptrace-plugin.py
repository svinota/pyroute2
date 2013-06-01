'''
The code is ported from python-ptrace's strace.py
'''
import sys
import socket
from pyroute2.common import Dotkeys

from ptrace.debugger import PtraceDebugger
from ptrace.debugger import Application
from ptrace.debugger import ProcessExit
from ptrace.debugger import ProcessSignal
from ptrace.debugger import NewProcessEvent
from ptrace.debugger import ProcessExecution

from ptrace.func_call import FunctionCallOptions


class SyscallTracer(Application):
    def __init__(self):
        Application.__init__(self)
        options = {'pid': None,
                   'fork': True,
                   'trace_exec': True,
                   'no_stdout': False,
                   'type': False,
                   'name': False,
                   'string_length': 256,
                   'raw_socketcall': False,
                   'address': False,
                   'array_count': 20,
                   'show_ip': False,
                   'enter': False}
        self.options = Dotkeys(options)
        self.program = sys.argv[1:]
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
                                  'send',
                                  'recvmsg',
                                  'sendmsg',
                                  'sendto') and \
                    syscall.arguments[0].value in self.monitor:
                print syscall.name
                print syscall.arguments

        # Break at next syscall
        process.syscall()

    def processExited(self, event):
        # Display syscall which has not exited
        state = event.process.syscall_state
        print state

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
                self.processExited(event)
                continue
            except ProcessSignal, event:
                event.display()
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
        except ProcessExit as e:
            self.processExited(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
        self.debugger.quit()

SyscallTracer().main()
