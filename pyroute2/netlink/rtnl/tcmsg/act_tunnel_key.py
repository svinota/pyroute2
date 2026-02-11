import struct

from pyroute2.netlink import NLA_F_NESTED, nla
from pyroute2.netlink.rtnl.tcmsg.common import CommonTcArgs, tc_actions
from pyroute2.netlink.rtnl.tcmsg.utils import is_ipv6_addr, parse_geneve_opt

# NLA attribute constants
TCA_TUNNEL_KEY_PARMS = 'TCA_TUNNEL_KEY_PARMS'
TCA_TUNNEL_KEY_ENC_IPV4_SRC = 'TCA_TUNNEL_KEY_ENC_IPV4_SRC'
TCA_TUNNEL_KEY_ENC_IPV4_DST = 'TCA_TUNNEL_KEY_ENC_IPV4_DST'
TCA_TUNNEL_KEY_ENC_IPV6_SRC = 'TCA_TUNNEL_KEY_ENC_IPV6_SRC'
TCA_TUNNEL_KEY_ENC_IPV6_DST = 'TCA_TUNNEL_KEY_ENC_IPV6_DST'
TCA_TUNNEL_KEY_ENC_KEY_ID = 'TCA_TUNNEL_KEY_ENC_KEY_ID'
TCA_TUNNEL_KEY_ENC_DST_PORT = 'TCA_TUNNEL_KEY_ENC_DST_PORT'
TCA_TUNNEL_KEY_ENC_OPTS = 'TCA_TUNNEL_KEY_ENC_OPTS'
TCA_TUNNEL_KEY_ENC_OPTS_GENEVE = 'TCA_TUNNEL_KEY_ENC_OPTS_GENEVE'
TCA_TUNNEL_KEY_ENC_OPT_GENEVE_CLASS = 'TCA_TUNNEL_KEY_ENC_OPT_GENEVE_CLASS'
TCA_TUNNEL_KEY_ENC_OPT_GENEVE_TYPE = 'TCA_TUNNEL_KEY_ENC_OPT_GENEVE_TYPE'
TCA_TUNNEL_KEY_ENC_OPT_GENEVE_DATA = 'TCA_TUNNEL_KEY_ENC_OPT_GENEVE_DATA'


# from include/uapi/linux/tc_act/tc_tunnel_key.h
class TunnelKeyConsts:
    TCA_TUNNEL_KEY_ACT_SET = 1
    TCA_TUNNEL_KEY_ACT_RELEASE = 2


ACTION_ARG_TO_CONST = {
    'set': TunnelKeyConsts.TCA_TUNNEL_KEY_ACT_SET,
    'unset': TunnelKeyConsts.TCA_TUNNEL_KEY_ACT_RELEASE,
}


class TunnelKeyArgs(CommonTcArgs):
    ACTION = 'action'
    KEY_ID = 'key_id'


def get_parameters(kwarg):
    if TunnelKeyArgs.ACTION not in kwarg:
        raise ValueError('action is required (set or unset)')
    action_str = kwarg[TunnelKeyArgs.ACTION].lower()
    if action_str not in ACTION_ARG_TO_CONST:
        raise ValueError('action must be one of: {}'.format(
            ', '.join(ACTION_ARG_TO_CONST.keys())))

    tunnel_action = ACTION_ARG_TO_CONST[action_str]

    if TunnelKeyArgs.TC_ACTION not in kwarg:
        raise ValueError('tc_action is required')

    tc_action_str = kwarg[TunnelKeyArgs.TC_ACTION]
    tc_action_code = tc_actions.get(tc_action_str)
    if tc_action_code is None:
        raise ValueError('unknown tc_action: {}'.format(tc_action_str))

    attrs = [[TCA_TUNNEL_KEY_PARMS, {
        't_action': tunnel_action,
        'action': tc_action_code,
    }]]

    if tunnel_action == TunnelKeyConsts.TCA_TUNNEL_KEY_ACT_RELEASE:
        return {'attrs': attrs}

    if tunnel_action == TunnelKeyConsts.TCA_TUNNEL_KEY_ACT_SET:
        attrs.extend(_build_tunnel_set_attrs(kwarg))
        return {'attrs': attrs}

    raise ValueError('unimplemented tunnel action')


def _build_tunnel_set_attrs(kwarg):
    attrs = []

    if TunnelKeyArgs.SRC_IP not in kwarg:
        raise ValueError('src_ip is required for tunnel_key set')
    if TunnelKeyArgs.DST_IP not in kwarg:
        raise ValueError('dst_ip is required for tunnel_key set')

    src_ip = kwarg[TunnelKeyArgs.SRC_IP]
    dst_ip = kwarg[TunnelKeyArgs.DST_IP]

    if is_ipv6_addr(src_ip):
        attrs.append([TCA_TUNNEL_KEY_ENC_IPV6_SRC, src_ip])
    else:
        attrs.append([TCA_TUNNEL_KEY_ENC_IPV4_SRC, src_ip])

    if is_ipv6_addr(dst_ip):
        attrs.append([TCA_TUNNEL_KEY_ENC_IPV6_DST, dst_ip])
    else:
        attrs.append([TCA_TUNNEL_KEY_ENC_IPV4_DST, dst_ip])

    if TunnelKeyArgs.KEY_ID in kwarg:
        key_id = int(kwarg[TunnelKeyArgs.KEY_ID])
        attrs.append([TCA_TUNNEL_KEY_ENC_KEY_ID, struct.pack('>I', key_id)])

    if TunnelKeyArgs.DST_PORT in kwarg:
        attrs.append([TCA_TUNNEL_KEY_ENC_DST_PORT, int(kwarg[TunnelKeyArgs.DST_PORT])])

    if TunnelKeyArgs.GENEVE_OPTS in kwarg:
        geneve_attrs = _build_geneve_opts(kwarg[TunnelKeyArgs.GENEVE_OPTS])
        attrs.append([TCA_TUNNEL_KEY_ENC_OPTS, {'attrs': geneve_attrs}])

    return attrs


def _build_geneve_opts(opts_str):
    opt_class, opt_type, opt_data = parse_geneve_opt(opts_str)

    return [[TCA_TUNNEL_KEY_ENC_OPTS_GENEVE, {
        'attrs': [
            [TCA_TUNNEL_KEY_ENC_OPT_GENEVE_CLASS, opt_class],
            [TCA_TUNNEL_KEY_ENC_OPT_GENEVE_TYPE, opt_type],
            [TCA_TUNNEL_KEY_ENC_OPT_GENEVE_DATA, opt_data],
        ]
    }]]


# from include/uapi/linux/tc_act/tc_tunnel_key.h
class options(nla):
    nla_flags = NLA_F_NESTED
    nla_map = (
        ('TCA_TUNNEL_KEY_UNSPEC', 'none'),
        ('TCA_TUNNEL_KEY_TM', 'none'),
        ('TCA_TUNNEL_KEY_PARMS', 'tca_tunnel_key_parms'),
        ('TCA_TUNNEL_KEY_ENC_IPV4_SRC', 'ip4addr'),
        ('TCA_TUNNEL_KEY_ENC_IPV4_DST', 'ip4addr'),
        ('TCA_TUNNEL_KEY_ENC_IPV6_SRC', 'ip6addr'),
        ('TCA_TUNNEL_KEY_ENC_IPV6_DST', 'ip6addr'),
        ('TCA_TUNNEL_KEY_ENC_KEY_ID', 'hex'),
        ('TCA_TUNNEL_KEY_PAD', 'none'),
        ('TCA_TUNNEL_KEY_ENC_DST_PORT', 'be16'),
        ('TCA_TUNNEL_KEY_NO_CSUM', 'uint8'),
        ('TCA_TUNNEL_KEY_ENC_OPTS', 'enc_opts'),
        ('TCA_TUNNEL_KEY_ENC_TOS', 'uint8'),
        ('TCA_TUNNEL_KEY_ENC_TTL', 'uint8'),
        ('TCA_TUNNEL_KEY_NO_FRAG', 'flag'),
    )

    class tca_tunnel_key_parms(nla):
        fields = (
            ('index', 'I'),
            ('capab', 'I'),
            ('action', 'i'),
            ('refcnt', 'i'),
            ('bindcnt', 'i'),
            ('t_action', 'i'),
        )

    class enc_opts(nla):
        nla_flags = NLA_F_NESTED
        nla_map = (
            ('TCA_TUNNEL_KEY_ENC_OPTS_UNSPEC', 'none'),
            ('TCA_TUNNEL_KEY_ENC_OPTS_GENEVE', 'geneve'),
        )

        class geneve(nla):
            nla_flags = NLA_F_NESTED
            nla_map = (
                ('TCA_TUNNEL_KEY_ENC_OPT_GENEVE_UNSPEC', 'none'),
                ('TCA_TUNNEL_KEY_ENC_OPT_GENEVE_CLASS', 'be16'),
                ('TCA_TUNNEL_KEY_ENC_OPT_GENEVE_TYPE', 'uint8'),
                ('TCA_TUNNEL_KEY_ENC_OPT_GENEVE_DATA', 'hex'),
            )
