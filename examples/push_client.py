from pyroute2 import IOCore

ioc = IOCore()
(uid, addr) = ioc.connect('tcp://localhost:9824')
realm = ioc.discover(addr, 'push')
ioc.push(realm, 'hello, world!')
ioc.release()
