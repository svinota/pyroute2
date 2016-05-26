from socket import htons
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.act_police import nla_plus_police
from pyroute2.netlink.rtnl.tcmsg.act_police import get_parameters \
    as ap_parameters


def fix_msg(msg, kwarg):
    msg['info'] = htons(kwarg.get('protocol', 0) & 0xffff) |\
        ((kwarg.get('prio', 0) << 16) & 0xffff0000)


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (
        ('classid', 'TCA_FW_CLASSID'),
        ('act', 'TCA_FW_ACT'),
        # ('police', 'TCA_FW_POLICE'),
        # Handled in ap_parameters
        ('indev', 'TCA_FW_INDEV'),
        ('mask', 'TCA_FW_MASK'),
    )

    if kwarg.get('rate'):
        ret['attrs'].append(['TCA_FW_POLICE', ap_parameters(kwarg)])

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class options(nla, nla_plus_police):
    nla_map = (('TCA_FW_UNSPEC', 'none'),
               ('TCA_FW_CLASSID', 'uint32'),
               ('TCA_FW_POLICE', 'police'),  # TODO string?
               ('TCA_FW_INDEV', 'hex'),  # TODO string
               ('TCA_FW_ACT', 'hex'),  # TODO
               ('TCA_FW_MASK', 'uint32'))
