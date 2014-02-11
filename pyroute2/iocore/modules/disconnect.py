from pyroute2.netlink import IPRCMD_DISCONNECT
from pyroute2.iocore.utils import access


target = IPRCMD_DISCONNECT
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    uid = cmd.get_attr('IPR_ATTR_UUID')
    broker.deregister_link(uid)
