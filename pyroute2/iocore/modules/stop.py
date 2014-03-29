from pyroute2.netlink import IPRCMD_STOP
from pyroute2.iocore.utils import access


target = IPRCMD_STOP
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    broker.shutdown_flag.set()
