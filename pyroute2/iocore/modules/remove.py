from pyroute2.netlink import IPRCMD_REMOVE
from pyroute2.iocore.utils import access


target = IPRCMD_REMOVE
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    if broker.providers.get(url, None) == sock:
        del broker.providers[url]
