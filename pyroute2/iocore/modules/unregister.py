from pyroute2.netlink import IPRCMD_UNREGISTER
from pyroute2.iocore.utils import access


target = IPRCMD_UNREGISTER
level = access.ANY


def command(broker, sock, env, cmd, rsp):
    broker.controls.remove(sock)
