'''
Netlink proxy engine
'''
import errno
import struct
import threading


class NetlinkInProxy(object):
    '''
    Incoming proxy::

        User -> NetlinkInProxy -> Kernel
                       |
             <---------+

    '''

    def __init__(self, rcvch, lock=None):
        self.rcvch = rcvch
        self.lock = lock or threading.Lock()
        self.pmap = {}

    def handle(self, data):
        #
        # match the packet
        #
        ptype = struct.unpack('H', data[4:6])[0]
        plugin = self.pmap.get(ptype, None)
        if plugin is not None:
            with self.lock:
                try:
                    if plugin(data, self.rcvch) is None:
                        msg = struct.pack('IHH', 20, 2, 0)
                        msg += data[8:16]
                        msg += struct.pack('I', 0)
                        self.rcvch.send(msg)

                except Exception as e:
                    # errmsg
                    if isinstance(e, OSError):
                        code = e.errno
                    else:
                        code = errno.ECOMM
                    msg = struct.pack('HH', 2, 0)
                    msg += data[8:16]
                    msg += struct.pack('I', code)
                    msg += data
                    msg = struct.pack('I', len(msg) + 4) + msg
                    self.rcvch.send(msg)
                return True
        return False
