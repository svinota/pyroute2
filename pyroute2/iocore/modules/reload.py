from pyroute2.netlink import IPRCMD_RELOAD


target = IPRCMD_RELOAD


def command(broker, sock, env, cmd, rsp):
    broker.ioloop.reload()
