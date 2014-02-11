from pyroute2.netlink import IPRCMD_REGISTER
from pyroute2.iocore.utils import access


target = IPRCMD_REGISTER
level = access.ANY


def command(broker, sock, env, cmd, rsp):
    # auth request
    secret = cmd.get_attr('IPR_ATTR_SECRET')
    if secret == broker.secret:
        broker.controls.add(sock)
