from pyroute2.netlink import IPRCMD_REGISTER


target = IPRCMD_REGISTER


def command(broker, sock, env, cmd, rsp):
    # auth request
    secret = cmd.get_attr('IPR_ATTR_SECRET')
    if secret == broker.secret:
        broker.controls.add(sock)
