from pyroute2.netlink.rtnl.tcmsg import em_ipset

plugins = {
           #0: em_container,
           #1: em_cmp,
           #2: em_nbyte,
           #3: em_u32,
           #4: em_meta,
           #5: em_text,
           #6: em_vlan,
           #7: em_canid,
           8: em_ipset,
           #9: em_ipt,
          }

plugins_translate = {
                    'container': 0,
                    'cmp': 1,
                    'nbyte': 2,
                    'u32': 3,
                    'meta': 4,
                    'text': 5,
                    'vlan': 6,
                    'canid': 7,
                    'ipset': 8,
                    'ipt': 9,
                    }


class nla_plus_tcf_ematch_opt(object):
    @staticmethod
    def parse_ematch_options(self, *argv, **kwarg):
        if 'kind' not in self:
            raise Exception('ematch requires "kind" parameter')

        kind = self['kind']
        if kind in plugins:
            return plugins[kind].options
        else:
            return self.hex
        return self.hex


def get_ematch_parms(kwarg):
    if 'kind' not in kwarg:
        raise Exception('ematch requires "kind" parameter')

    if kwarg['kind'] in plugins:
        return plugins[kwarg['kind']].get_parameters(kwarg)
    else:
        return []


def get_tcf_ematches(kwarg):
    ret = {'attrs': []}

    kind = kwarg['match'][0]['kind']

    # Translate string kind into numeric kind
    kind = plugins_translate[kind]

    # Not sure if really needed
    #ret['attrs'].append(['TCF_EM_KIND'], kind)

    # Load plugin and transfer data
    return plugins[kind].set_parameters(kwarg)
