'''
Netlink proxy engine
'''
import errno
import struct
import threading


class NetlinkProxy(object):
    '''
    Proxy schemes::

        User -> NetlinkProxy -> Kernel
                       |
             <---------+

        User <- NetlinkProxy <- Kernel

    '''

    def __init__(self, policy='forward', nl=None, lock=None):
        self.nl = nl
        self.lock = lock or threading.Lock()
        self.pmap = {}
        self.policy = policy

    def handle(self, data):
        #
        # match the packet
        #
        ptype = struct.unpack('H', data[4:6])[0]
        plugin = self.pmap.get(ptype, None)
        if plugin is not None:
            with self.lock:
                try:
                    ret = plugin(data, self.nl)
                    if ret is None:
                        msg = struct.pack('IHH', 20, 2, 0)
                        msg += data[8:16]
                        msg += struct.pack('I', 0)
                        return {'verdict': self.policy,
                                'data': msg}
                    else:
                        return ret

                except Exception as e:
                    # errmsg
                    if isinstance(e, (OSError, IOError)):
                        code = e.errno
                    else:
                        code = errno.ECOMM
                    msg = struct.pack('HH', 2, 0)
                    msg += data[8:16]
                    msg += struct.pack('I', code)
                    msg += data
                    msg = struct.pack('I', len(msg) + 4) + msg
                    return {'verdict': 'error',
                            'data': msg}
        return None
