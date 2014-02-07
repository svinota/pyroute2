'''
Push/pull using raw IOCore

tcp -- control connection
udp -- data push
'''
from pyroute2 import IOCore
from pyroute2.iocore import NLT_DGRAM


ioc1 = IOCore()
ioc1.serve('tcp://0.0.0.0:9824')
ioc1.serve('udp://0.0.0.0:9824')
ioc1.provide('push')

ioc2 = IOCore()
(uid, addr) = ioc2.connect('tcp://localhost:9824')
ioc2.connect('udp://localhost:9824')
port = ioc2.discover('push', addr)
ioc2.push((addr, port), 'hello, world!', NLT_DGRAM)

print('waiting message from client')
ioc1.monitor()
msg = ioc1.get()[0]

print(msg)
ioc2.release()
ioc1.release()
