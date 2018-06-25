from socket import htons
from pyroute2 import protocols
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.common import TCA_ACT_MAX_PRIO
from pyroute2.netlink.rtnl.tcmsg.common_act import get_tca_action
from pyroute2.netlink.rtnl.tcmsg.common_act import nla_plus_tca_act_opt


def fix_msg(msg, kwarg):
    if 'protocol' not in kwarg:
        msg['info'] = htons(protocols.ETH_P_ALL & 0xffff) |\
            ((kwarg.get('prio', 0) << 16) & 0xffff0000)
    else:
        msg['info'] = htons(kwarg.get('protocol', 0) & 0xffff) |\
            ((kwarg.get('prio', 0) << 16) & 0xffff0000)


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (
        ('classid', 'TCA_MATCHALL_CLASSID'),
        ('flags', 'TCA_MATCHALL_FLAGS')
    )

    if kwarg.get('action'):
        ret['attrs'].append(['TCA_MATCHALL_ACT', get_tca_action(kwarg)])

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class options(nla):
    nla_map = (('TCA_MATCHALL_UNSPEC', 'none'),
               ('TCA_MATCHALL_CLASSID', 'be32'),
               ('TCA_MATCHALL_ACT', 'tca_act_prio'),
               ('TCA_MATCHALL_FLAGS', 'be32'))

    class tca_act_prio(nla):
        nla_map = tuple([('TCA_ACT_PRIO_%i' % x, 'tca_act') for x
                         in range(TCA_ACT_MAX_PRIO)])

        class tca_act(nla,
                      nla_plus_tca_act_opt):
            nla_map = (('TCA_ACT_UNSPEC', 'none'),
                       ('TCA_ACT_KIND', 'asciiz'),
                       ('TCA_ACT_OPTIONS', 'get_act_options'),
                       ('TCA_ACT_INDEX', 'hex'))
