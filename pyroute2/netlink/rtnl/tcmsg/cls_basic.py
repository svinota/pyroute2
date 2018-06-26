import struct
from socket import htons
from pyroute2 import protocols
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.common_ematch import get_tcf_ematches
from pyroute2.netlink.rtnl.tcmsg.common_ematch import nla_plus_tcf_ematch_opt

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
        ('action', 'TCA_BASIC_ACT'),
        ('classid', 'TCA_BASIC_CLASSID'),
        #('match', 'TCA_BASIC_EMATCHES'),
    )

    if kwarg.get('match'):
        ret['attrs'].append(['TCA_BASIC_EMATCHES', get_tcf_ematches(kwarg)])

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class options(nla):
    nla_map = (('TCA_BASIC_UNSPEC', 'none'),
               ('TCA_BASIC_CLASSID', 'uint32'),
               ('TCA_BASIC_EMATCHES', 'parse_basic_ematch_tree'),
               ('TCA_BASIC_ACT', 'hex'),
               ('TCA_BASIC_POLICE', 'hex'),
              )


    class parse_basic_ematch_tree(nla):
        nla_map = (('TCA_EMATCH_TREE_UNSPEC', 'none'),
                   ('TCA_EMATCH_TREE_HDR', 'tcf_parse_header'),
                   ('TCA_EMATCH_TREE_LIST', '*tcf_parse_list'),
                  )


        class tcf_parse_header(nla):
            fields = (('nmatches', 'H'),
                      ('progid', 'H'),
                     )


        class tcf_parse_list(nla, nla_plus_tcf_ematch_opt):
            fields = (('matchid', 'H'),
                      ('kind', 'H'),
                      ('flags', 'H'),
                      ('pad', 'H'),
                     )

            def decode(self):
                nla.decode(self)
                size = 0
                for field in self.fields + self.header:
                    size += struct.calcsize(field[1])

                start = self.offset + size
                end = start + (self.length - size)
                data = self.data[start:end]
                # TODO: it does not work :(
                self['opt'] = self.parse_ematch_options(self, data)(data=data)
