from pyroute2.netlink import IPRCMD_RELOAD
from pyroute2.iocore.utils import access


target = IPRCMD_RELOAD
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    broker.ioloop.reload()
