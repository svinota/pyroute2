from pyroute2 import IPRoute

ipr = IPRoute()

for msg in ipr.get_addr():
    print(msg)

ipr.close()
