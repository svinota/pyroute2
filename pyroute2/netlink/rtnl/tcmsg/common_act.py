from pyroute2.netlink.rtnl.tcmsg import act_gact
from pyroute2.netlink.rtnl.tcmsg import act_bpf
from pyroute2.netlink.rtnl.tcmsg import act_police
from pyroute2.netlink.rtnl.tcmsg import act_mirred
from pyroute2.netlink.rtnl.tcmsg import act_connmark

plugins = {'gact': act_gact,
           'bpf': act_bpf,
           'police': act_police,
           'mirred': act_mirred,
           'connmark': act_connmark,
           }


class nla_plus_tca_act_opt(object):
    @staticmethod
    def get_act_options(self, *argv, **kwarg):
        kind = self.get_attr('TCA_ACT_KIND')
        if kind in plugins:
            return plugins[kind].options
        else:
            return self.hex
        return self.hex


def get_act_parms(kwarg):
    if 'kind' not in kwarg:
        raise Exception('action requires "kind" parameter')

    if kwarg['kind'] in plugins:
        return plugins[kwarg['kind']].get_parameters(kwarg)
    else:
        return []


# All filters can use any act type, this is a generic parser for all
def get_tca_action(kwarg):
    ret = {'attrs': []}

    act = kwarg.get('action', 'drop')

    # convert simple action='..' to kwarg style
    if isinstance(act, str):
        act = {'kind': 'gact', 'action': act}

    # convert single dict action to first entry in a list of actions
    acts = act if isinstance(act, list) else [act]

    for i, act in enumerate(acts, start=1):
        opt = {'attrs': [['TCA_ACT_KIND', act['kind']],
                         ['TCA_ACT_OPTIONS', get_act_parms(act)]]}
        ret['attrs'].append(['TCA_ACT_PRIO_%d' % i, opt])

    return ret
