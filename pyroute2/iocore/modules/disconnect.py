from pyroute2.netlink import IPRCMD_DISCONNECT


target = IPRCMD_DISCONNECT


def command(broker, sock, env, cmd, rsp):
    uid = cmd.get_attr('IPR_ATTR_UUID')
    broker.deregister_link(uid)
