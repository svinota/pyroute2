'''
Simple taskstats sample.
'''
import os
from pyroute2 import TaskStats
from pyroute2.common import hexdump

pid = os.getpid()
ts = TaskStats()
# bind is required in the case of generic netlink
ts.bind()
ret = ts.get_pid_stat(int(pid))[0]
# raw hex structure to check alignment
print(hexdump(ret.raw))
# parsed structure
print(ret)
ts.close()
