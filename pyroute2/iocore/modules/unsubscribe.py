from pyroute2.netlink import IPRCMD_UNSUBSCRIBE
from pyroute2.iocore.utils import access


target = IPRCMD_UNSUBSCRIBE
level = access.ANY


def command(broker, sock, env, cmd, rsp):
    cid = cmd.get_attr('IPR_ATTR_CID')
    if cid in broker.subscribe:
        del broker.subscribe[cid]
        broker._cid.append(cid)
