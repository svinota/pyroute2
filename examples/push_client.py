from pyroute2 import IOCore
from pyroute2.iocore import NLT_DGRAM

ioc = IOCore()
(uid, addr) = ioc.connect('tcp://localhost:9824')
ioc.connect('udp://localhost:9824')
port = ioc.discover('push', addr)
ioc.push((addr, port), 'hello, world!', NLT_DGRAM)
ioc.release()
