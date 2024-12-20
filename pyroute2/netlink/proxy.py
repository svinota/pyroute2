'''
Netlink proxy engine
'''

import errno
import logging
import multiprocessing
import struct
import traceback

from pyroute2.common import msg_done
from pyroute2.netlink.exceptions import NetlinkError

log = logging.getLogger(__name__)


class NetlinkProxy:
    def __init__(self, pmap, netns=None):
        self.pmap = pmap
        self.netns = netns

    def run(self, plugin, msg):
        channel = multiprocessing.Queue()
        if self.netns is None:
            plugin(msg, None, channel)
        else:
            child = multiprocessing.Process(
                target=plugin, args=(msg, self.netns, channel), daemon=True
            )
            child.start()
            child.join(30)
            child.kill()
            child.join(1)
            if child.exitcode < 0:
                raise TimeoutError(errno.ETIMEDOUT, 'cancelled plugin call')
        try:
            ret = channel.get(timeout=5)
        except Exception:
            raise
        finally:
            channel.close()
        if isinstance(ret, Exception):
            raise ret
        return ret

    def handle(self, msg):
        ptype = msg['header']['type']
        plugin = self.pmap.get(ptype, None)
        if plugin is not None:
            try:
                #
                # The request is terminated in the plugin,
                # return the NLMSG_ERR == 0
                #
                ret = self.run(plugin, msg)
                if ret is None:
                    return msg_done(msg)
                return ret
            except Exception as e:
                log.error(''.join(traceback.format_stack()))
                log.error(traceback.format_exc())
                # errmsg
                if isinstance(e, (OSError, IOError)):
                    code = e.errno or errno.ENODATA
                elif isinstance(e, NetlinkError):
                    code = e.code
                else:
                    code = errno.ECOMM
                newmsg = struct.pack('HH', 2, 0)
                newmsg += msg.data[8:16]
                newmsg += struct.pack('I', code)
                newmsg += msg.data
                newmsg = struct.pack('I', len(newmsg) + 4) + newmsg
                return newmsg
        return b''
