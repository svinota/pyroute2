'''
devlink module
==============
'''
from pyroute2.common import map_namespace
from pyroute2.netlink import genlmsg
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.nlsocket import Marshal

# devlink commands
DEVLINK_CMD_UNSPEC = 0
DEVLINK_CMD_GET = 1
DEVLINK_CMD_SET = 2
DEVLINK_CMD_NEW = 3
DEVLINK_CMD_DEL = 4
DEVLINK_CMD_PORT_GET = 5
DEVLINK_CMD_PORT_SET = 6
DEVLINK_CMD_PORT_NEW = 7
DEVLINK_CMD_PORT_DEL = 8
DEVLINK_CMD_PORT_SPLIT = 9
DEVLINK_CMD_PORT_UNSPLIT = 10
DEVLINK_CMD_SB_GET = 11
DEVLINK_CMD_SB_SET = 12
DEVLINK_CMD_SB_NEW = 13
DEVLINK_CMD_SB_DEL = 14
DEVLINK_CMD_SB_POOL_GET = 15
DEVLINK_CMD_SB_POOL_SET = 16
DEVLINK_CMD_SB_POOL_NEW = 17
DEVLINK_CMD_SB_POOL_DEL = 18
DEVLINK_CMD_SB_PORT_POOL_GET = 19
DEVLINK_CMD_SB_PORT_POOL_SET = 20
DEVLINK_CMD_SB_PORT_POOL_NEW = 21
DEVLINK_CMD_SB_PORT_POOL_DEL = 22
DEVLINK_CMD_SB_TC_POOL_BIND_GET = 23
DEVLINK_CMD_SB_TC_POOL_BIND_SET = 24
DEVLINK_CMD_SB_TC_POOL_BIND_NEW = 25
DEVLINK_CMD_SB_TC_POOL_BIND_DEL = 26
DEVLINK_CMD_SB_OCC_SNAPSHOT = 27
DEVLINK_CMD_SB_OCC_MAX_CLEAR = 28
DEVLINK_CMD_MAX = DEVLINK_CMD_SB_OCC_MAX_CLEAR

(DEVLINK_NAMES, DEVLINK_VALUES) = map_namespace('DEVLINK_CMD_', globals())

# port type
DEVLINK_PORT_TYPE_NOTSET = 0
DEVLINK_PORT_TYPE_AUTO = 1
DEVLINK_PORT_TYPE_ETH = 2
DEVLINK_PORT_TYPE_IB = 3

# threshold type
DEVLINK_SB_POOL_TYPE_INGRESS = 0
DEVLINK_SB_POOL_TYPE_EGRESS = 1

DEVLINK_SB_THRESHOLD_TO_ALPHA_MAX = 20


class devlinkcmd(genlmsg):
    prefix = 'DEVLINK_ATTR_'
    nla_map = (('DEVLINK_ATTR_UNSPEC', 'none'),
               ('DEVLINK_ATTR_BUS_NAME', 'asciiz'),
               ('DEVLINK_ATTR_DEV_NAME', 'asciiz'),
               ('DEVLINK_ATTR_PORT_INDEX', 'uint32'),
               ('DEVLINK_ATTR_PORT_TYPE', 'uint16'),
               ('DEVLINK_ATTR_PORT_DESIRED_TYPE', 'uint16'),
               ('DEVLINK_ATTR_PORT_NETDEV_IFINDEX', 'uint32'),
               ('DEVLINK_ATTR_PORT_NETDEV_NAME', 'asciiz'),
               ('DEVLINK_ATTR_PORT_IBDEV_NAME', 'asciiz'),
               ('DEVLINK_ATTR_PORT_SPLIT_COUNT', 'uint32'),
               ('DEVLINK_ATTR_PORT_SPLIT_GROUP', 'uint32'),
               ('DEVLINK_ATTR_SB_INDEX', 'uint32'),
               ('DEVLINK_ATTR_SB_SIZE', 'uint32'),
               ('DEVLINK_ATTR_SB_INGRESS_POOL_COUNT', 'uint16'),
               ('DEVLINK_ATTR_SB_EGRESS_POOL_COUNT', 'uint16'),
               ('DEVLINK_ATTR_SB_INGRESS_TC_COUNT', 'uint16'),
               ('DEVLINK_ATTR_SB_EGRESS_TC_COUNT', 'uint16'),
               ('DEVLINK_ATTR_SB_POOL_INDEX', 'uint16'),
               ('DEVLINK_ATTR_SB_POOL_TYPE', 'uint8'),
               ('DEVLINK_ATTR_SB_POOL_SIZE', 'uint32'),
               ('DEVLINK_ATTR_SB_POOL_THRESHOLD_TYPE', 'uint8'),
               ('DEVLINK_ATTR_SB_THRESHOLD', 'uint32'),
               ('DEVLINK_ATTR_SB_TC_INDEX', 'uint16'),
               ('DEVLINK_ATTR_SB_OCC_CUR', 'uint32'),
               ('DEVLINK_ATTR_SB_OCC_MAX', 'uint32'))


class MarshalDevlink(Marshal):
    msg_map = {DEVLINK_CMD_UNSPEC: devlinkcmd,
               DEVLINK_CMD_GET: devlinkcmd,
               DEVLINK_CMD_SET: devlinkcmd,
               DEVLINK_CMD_NEW: devlinkcmd,
               DEVLINK_CMD_DEL: devlinkcmd,
               DEVLINK_CMD_PORT_GET: devlinkcmd,
               DEVLINK_CMD_PORT_SET: devlinkcmd,
               DEVLINK_CMD_PORT_NEW: devlinkcmd,
               DEVLINK_CMD_PORT_DEL: devlinkcmd,
               DEVLINK_CMD_PORT_SPLIT: devlinkcmd,
               DEVLINK_CMD_PORT_UNSPLIT: devlinkcmd,
               DEVLINK_CMD_SB_GET: devlinkcmd,
               DEVLINK_CMD_SB_SET: devlinkcmd,
               DEVLINK_CMD_SB_NEW: devlinkcmd,
               DEVLINK_CMD_SB_DEL: devlinkcmd,
               DEVLINK_CMD_SB_POOL_GET: devlinkcmd,
               DEVLINK_CMD_SB_POOL_SET: devlinkcmd,
               DEVLINK_CMD_SB_POOL_NEW: devlinkcmd,
               DEVLINK_CMD_SB_POOL_DEL: devlinkcmd,
               DEVLINK_CMD_SB_PORT_POOL_GET: devlinkcmd,
               DEVLINK_CMD_SB_PORT_POOL_SET: devlinkcmd,
               DEVLINK_CMD_SB_PORT_POOL_NEW: devlinkcmd,
               DEVLINK_CMD_SB_PORT_POOL_DEL: devlinkcmd,
               DEVLINK_CMD_SB_TC_POOL_BIND_GET: devlinkcmd,
               DEVLINK_CMD_SB_TC_POOL_BIND_SET: devlinkcmd,
               DEVLINK_CMD_SB_TC_POOL_BIND_NEW: devlinkcmd,
               DEVLINK_CMD_SB_TC_POOL_BIND_DEL: devlinkcmd,
               DEVLINK_CMD_SB_OCC_SNAPSHOT: devlinkcmd,
               DEVLINK_CMD_SB_OCC_MAX_CLEAR: devlinkcmd}

    def fix_message(self, msg):
        try:
            msg['event'] = DEVLINK_VALUES[msg['cmd']]
        except Exception:
            pass


class DevlinkSocket(GenericNetlinkSocket):
    def __init__(self):
        GenericNetlinkSocket.__init__(self)
        self.marshal = MarshalDevlink()

    def bind(self, groups=0, async=False):
        GenericNetlinkSocket.bind(self, 'devlink', devlinkcmd,
                                  groups, None, async)
