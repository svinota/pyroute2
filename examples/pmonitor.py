'''
Monitor process exit
'''
import sys
from pyroute2 import TaskStats
from pyroute2.common import hexdump

pmask = sys.argv[-1] if len(sys.argv) > 1 else "1"
ts = TaskStats()
ts.register_mask(pmask)
while True:
    try:
        msg = ts.get()[0]
    except KeyboardInterrupt:
        break
    print(hexdump(msg.raw))
    print(msg)

ts.deregister_mask(pmask)
