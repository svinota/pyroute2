from pyroute2.netlink import nla
from pyroute2.netlink import NLA_F_NESTED
from pyroute2.netlink.rtnl.tcmsg.common import (
    tc_actions,
    TC_ACT_GOTO_CHAIN,
    TC_ACT_EXT_VAL_MASK,
)


class options(nla):
    nla_flags = NLA_F_NESTED
    nla_map = (('TCA_GACT_UNSPEC', 'none'),
               ('TCA_GACT_TM', 'none'),
               ('TCA_GACT_PARMS', 'tca_gact_parms'),
               ('TCA_GACT_PROB', 'none'))

    class tca_gact_parms(nla):
        fields = (('index', 'I'),
                  ('capab', 'I'),
                  ('action', 'i'),
                  ('refcnt', 'i'),
                  ('bindcnt', 'i'))


def get_parameters(kwarg):
    ret = {'attrs': []}
    action_name = kwarg.get('action', 'drop')

    if action_name == 'goto':
        if 'chain' not in kwarg:
            raise ValueError("'goto' action requires 'chain' parameter")

        chain_id = int(kwarg['chain'])

        if chain_id < 0 or chain_id > TC_ACT_EXT_VAL_MASK:
            raise ValueError(
                "chain id must be between 0 and {}".format(TC_ACT_EXT_VAL_MASK)
            )

        action_value = TC_ACT_GOTO_CHAIN | chain_id
    else:
        action_value = tc_actions[action_name]

    ret['attrs'].append(['TCA_GACT_PARMS', {'action': action_value}])
    return ret
