from pprint import pprint
from pyroute2.netlink.rtnl.tcmsg import tcmsg
import io
import sys


f = open(sys.argv[1], 'r')
b = io.BytesIO()

for a in f.readlines():
    if a[0] == '#':
        continue
    while True:
        try:
            b.write(chr(int(a[2:4], 16)))
        except:
            break
        a = a[4:]

b.seek(0)
t = tcmsg(b)
t.decode()
pprint(t)
