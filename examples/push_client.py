from pyroute2 import IOCore

ioc = IOCore()
(uid, addr) = ioc.connect('tcp://localhost:9824')
port = ioc.discover(addr, 'push')
ioc.push(addr, port, 'hello, world!')
ioc.release()
