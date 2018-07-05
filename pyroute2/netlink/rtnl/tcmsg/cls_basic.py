'''
basic
+++++

Basic filter type supports ipset matches::

    # Prepare a simple match on an ipset at index 0 src
    # (the first ipset name that appears when running `ipset list`
    match = [{"index": 0, "mode": "src"}]
    ip.tc("add-filter", "basic", ifb0, em_kind="ipset",
          parent=0x10000, classid=0x10010, match=match)

    # The same match but inverted, simply add inverse flag
    match = [{"index": 0, "mode": "src", "inverse": True}]
    ip.tc("add-filter", "basic", ifb0, em_kind="ipset",
          parent=0x10000, classid=0x10010, match=match)

    # Still one ipset but with multiple dimensions:
    # comma separated list of modes
    match = [{"index": 0, "mode": "src,dst"}]
    ip.tc("add-filter", "basic", ifb0, em_kind="ipset",
          parent=0x10000, classid=0x10010, match=match)

    # Now let's add multiple expressions (ipset 0 src and ipset 1 src)
    match = [{"index": 0, "mode": "src", "relation": "and"},
             {"index": 1, "mode": "src"}]
    ip.tc("add-filter", "basic", ifb0, em_kind="ipset",
          parent=0x10000, classid=0x10010, match=match)

    # The same works with OR (ipset 0 src or ipset 1 src)
    match = [{"index": 0, "mode": "src", "relation": "OR"},
             {"index": 1, "mode": "src"}]
    ip.tc("add-filter", "basic", ifb0, em_kind="ipset",
          parent=0x10000, classid=0x10010, match=match)

NOTES:
    When not specified, `inverse` flag is set to False.
    Do not specify `relation` keyword on the last expression or
    if there is only one expression.
    `relation` can be written using multiple format:
      "and", "AND", "&&", "or", "OR", "||"
'''

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
                      ('opt', 's'),
                      )

            def decode(self):
                nla.decode(self)
                size = 0
                for field in self.fields + self.header:
                    if 'opt' in field:
                        # Ignore this field as it a hack used to brain encoder
                        continue
                    size += struct.calcsize(field[1])

                start = self.offset + size
                end = self.offset + self.length
                data = self.data[start:end]
                self['opt'] = self.parse_ematch_options(self, data)
