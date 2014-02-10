from pyroute2.netlink import IPRCMD_SUBSCRIBE


target = IPRCMD_SUBSCRIBE


def command(broker, sock, env, cmd, rsp):
    cid = broker._cid.pop()
    broker.subscribe[cid] = {'socket': sock,
                             'keys': []}
    for key in cmd.get_attrs('IPR_ATTR_KEY'):
        target = (key['offset'],
                  key['key'],
                  key['mask'])
        broker.subscribe[cid]['keys'].append(target)
    rsp['attrs'].append(['IPR_ATTR_CID', cid])
