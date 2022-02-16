'''
'''

from socket import htons
from pr2modules.netlink import nla
from pr2modules.netlink.rtnl import TC_H_ROOT
from pr2modules.netlink import NLA_F_NESTED
from pr2modules.protocols import ETH_P_ALL
from pr2modules.netlink.rtnl.tcmsg.common import stats2
from pr2modules.netlink.rtnl.tcmsg.common import TCA_ACT_MAX_PRIO
from pr2modules.netlink.rtnl.tcmsg.common_act import get_tca_action
from pr2modules.netlink.rtnl.tcmsg.common_act import nla_plus_tca_act_opt
from pr2modules.netlink.rtnl.tcmsg.act_police import nla_plus_police
from pr2modules.netlink.rtnl.tcmsg.act_police import (
    get_parameters as ap_parameters,
)

parent = TC_H_ROOT
TCA_BPF_FLAG_ACT_DIRECT = 1


def fix_msg(msg, kwarg):
    msg['info'] = htons(kwarg.pop('protocol', ETH_P_ALL) & 0xFFFF) | (
        (kwarg.pop('prio', 0) << 16) & 0xFFFF0000
    )


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (
        # ('action', 'TCA_BPF_ACT'),
        # ('police', 'TCA_BPF_POLICE'),
        ('classid', 'TCA_BPF_CLASSID'),
        ('fd', 'TCA_BPF_FD'),
        ('name', 'TCA_BPF_NAME'),
        ('flags', 'TCA_BPF_FLAGS'),
    )

    act = kwarg.get('action')
    if act:
        ret['attrs'].append(['TCA_BPF_ACT', get_tca_action(kwarg)])

    if kwarg.get('rate'):
        ret['attrs'].append(['TCA_BPF_POLICE', ap_parameters(kwarg)])

    kwarg['flags'] = kwarg.get('flags', 0)
    if kwarg.get('direct_action', False):
        kwarg['flags'] |= TCA_BPF_FLAG_ACT_DIRECT

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class options(nla, nla_plus_police):
    nla_map = (
        ('TCA_BPF_UNSPEC', 'none'),
        ('TCA_BPF_ACT', 'bpf_act'),
        ('TCA_BPF_POLICE', 'police'),
        ('TCA_BPF_CLASSID', 'uint32'),
        ('TCA_BPF_OPS_LEN', 'uint32'),
        ('TCA_BPF_OPS', 'uint32'),
        ('TCA_BPF_FD', 'uint32'),
        ('TCA_BPF_NAME', 'asciiz'),
        ('TCA_BPF_FLAGS', 'uint32'),
    )

    class bpf_act(nla):
        nla_flags = NLA_F_NESTED
        nla_map = tuple(
            [
                ('TCA_ACT_PRIO_%i' % x, 'tca_act_bpf')
                for x in range(TCA_ACT_MAX_PRIO)
            ]
        )

        class tca_act_bpf(nla, nla_plus_tca_act_opt):
            nla_map = (
                ('TCA_ACT_UNSPEC', 'none'),
                ('TCA_ACT_KIND', 'asciiz'),
                ('TCA_ACT_OPTIONS', 'get_act_options'),
                ('TCA_ACT_INDEX', 'hex'),
                ('TCA_ACT_STATS', 'get_stats2'),
            )

            @staticmethod
            def get_stats2(self, *argv, **kwarg):
                return stats2
