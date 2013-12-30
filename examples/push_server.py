from pyroute2 import IOCore

ioc = IOCore()
ioc.serve('tcp://0.0.0.0:9824')
ioc.serve('udp://0.0.0.0:9824')
ioc.provide('push')

print('waiting message from client')
ioc.monitor()
msg = ioc.get()[0]

print(msg)
ioc.release()
