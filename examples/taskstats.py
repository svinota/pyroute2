'''
Simple taskstats sample.
'''
import os
from pyroute2 import TaskStats
from pyroute2.common import hexdump

pid = os.getpid()
ts = TaskStats()
ret = ts.get_pid_stat(int(pid))[0]
# raw hex structure to check alignment
print(hexdump(ret.raw))
# parsed structure
print(ret)
ts.release()
