from pyroute2.netlink import IPRCMD_SHUTDOWN


target = IPRCMD_SHUTDOWN


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    old_sock = broker.sockets[url]
    del broker.sockets[url]
    broker._rlist.remove(old_sock)
    broker.servers.remove(old_sock)
    broker.ioloop.unregister(old_sock)
