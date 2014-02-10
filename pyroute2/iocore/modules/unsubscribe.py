from pyroute2.netlink import IPRCMD_UNSUBSCRIBE


target = IPRCMD_UNSUBSCRIBE


def command(broker, sock, env, cmd, rsp):
    cid = cmd.get_attr('IPR_ATTR_CID')
    if cid in broker.subscribe:
        del broker.subscribe[cid]
        broker._cid.append(cid)
