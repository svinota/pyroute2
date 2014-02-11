from pyroute2.netlink import IPRCMD_PROVIDE
from pyroute2.iocore.utils import access


target = IPRCMD_PROVIDE
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    if url not in broker.providers:
        broker.providers[url] = sock
