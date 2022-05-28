'''
Monitor process exit
'''
from pyroute2 import TaskStats
from pyroute2.common import hexdump

pmask = ''

with open('/proc/cpuinfo', 'r') as f:
    for line in f.readlines():
        if line.startswith('processor'):
            pmask += ',' + line.split()[2]
pmask = pmask[1:]
ts = TaskStats()
ts.register_mask(pmask)
msg = ts.get()[0]
print(hexdump(msg.raw))
print(msg)

ts.deregister_mask(pmask)
ts.release()
