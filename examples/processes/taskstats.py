'''
Simple taskstats sample.
'''
import os
from pyroute2 import TaskStats

pid = os.getpid()
ts = TaskStats()
# bind is required in the case of generic netlink
ts.bind()
ret = ts.get_pid_stat(int(pid))[0]
# parsed structure
print(ret)
ts.close()
