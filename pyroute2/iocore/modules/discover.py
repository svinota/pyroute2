from pyroute2.netlink import IPRCMD_DISCOVER


target = IPRCMD_DISCOVER


def command(broker, sock, env, cmd, rsp):
    # .. _ioc-discover:
    url = cmd.get_attr('IPR_ATTR_HOST')
    if url in broker.discover:
        rsp['attrs'].append(['IPR_ATTR_ADDR', broker.discover[url]])
