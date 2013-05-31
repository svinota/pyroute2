#!/usr/bin/python

import pprint

from pyroute2 import IPRoute

ip = IPRoute()
ip.monitor()
while True:
    print("--------------------------------------------------------------")
    pprint.pprint(ip.get())
