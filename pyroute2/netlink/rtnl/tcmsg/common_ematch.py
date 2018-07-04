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
            ret = plugins[kind].data(data=argv[0])
            ret.decode()
            return ret
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
    header = {'nmatches': 1,
              'progid': 0}

    match = {'matchid': 0,
             'kind': None,
             'flags': 0,
             'pad': 0,
             'opt': None}

    kind = kwarg['em_kind']

    # Translate string kind into numeric kind
    kind = plugins_translate[kind]
    match['kind'] = kind

    # Load plugin and transfer data
    data = plugins[kind].data()
    data.setvalue(kwarg['match'][0])
    data.encode()

    match['opt'] = data.data.decode('utf-8')
    #match['flags'] = data.get('attrs')[1].get('flags')

    ret['attrs'].append(['TCA_EMATCH_TREE_HDR', header])
    ret['attrs'].append(['TCA_EMATCH_TREE_LIST', [match]])

    return ret
