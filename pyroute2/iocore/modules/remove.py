from pyroute2.netlink import IPRCMD_REMOVE


target = IPRCMD_REMOVE


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    if broker.providers.get(url, None) == sock:
        del broker.providers[url]
