from pyroute2.netlink import IPRCMD_SHUTDOWN
from pyroute2.iocore.utils import access


target = IPRCMD_SHUTDOWN
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    old_sock = broker.sockets[url]
    del broker.sockets[url]
    broker._rlist.remove(old_sock)
    broker.servers.remove(old_sock)
    broker.ioloop.unregister(old_sock)
    old_sock.close()
