#!/usr/bin/python

import pprint

from pyroute2 import iproute

ip = iproute()
ip.monitor()
while True:
    print("--------------------------------------------------------------")
    pprint.pprint(ip.get(interruptible=True))
