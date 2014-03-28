from pyroute2.netlink import IPRCMD_DISCOVER
from pyroute2.iocore.utils import access


target = IPRCMD_DISCOVER
level = access.ANY


def command(broker, sock, env, cmd, rsp):
    # .. _ioc-discover:
    url = cmd.get_attr('IPR_ATTR_HOST')
    rsp['attrs'].append(['IPR_ATTR_ADDR', broker.discover[url]])
