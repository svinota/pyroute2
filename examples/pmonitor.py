'''
Monitor process exit
'''
from pyroute2 import TaskStats
from pyroute2.common import hexdump

pmask = "1"
ts = TaskStats()
ts.register_mask(pmask)
msg = ts.get()[0]
print(hexdump(msg.raw))
print(msg)

ts.deregister_mask(pmask)
ts.release()
