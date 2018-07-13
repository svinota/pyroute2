'''
flow
++++

Flow filter supports two types of modes::
    - map
    - hash

    # Prepare a Qdisc with fq-codel
    ip.tc("add", "fq_codel", ifb0,
          parent=0x10001, handle=0x10010)

    # Create flow filter with hash mode
    # Single:
    keys = "src"
    # Multi (comma separated list of keys):
    keys = "src,nfct-src"
    ip.tc("add-filter", "flow", ifb0,
          mode="hash", keys=keys,
          divisor=1024, perturb=60,
          handle=0x10, baseclass=0x10010,
          parent=0x10001)
'''

from socket import htons
from pyroute2 import protocols
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.common import get_tca_mode
from pyroute2.netlink.rtnl.tcmsg.common import get_tca_keys
from pyroute2.netlink.rtnl.tcmsg.common import tc_flow_keys
from pyroute2.netlink.rtnl.tcmsg.common import tc_flow_modes


def fix_msg(msg, kwarg):
    if 'protocol' not in kwarg:
        msg['info'] = htons(protocols.ETH_P_ALL & 0xffff) |\
            ((kwarg.get('prio', 0) << 16) & 0xffff0000)
    else:
        msg['info'] = htons(kwarg.get('protocol', 0) & 0xffff) |\
            ((kwarg.get('prio', 0) << 16) & 0xffff0000)


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (('baseclass', 'TCA_FLOW_BASECLASS'),
                 ('divisor', 'TCA_FLOW_DIVISOR'),
                 ('perturb', 'TCA_FLOW_PERTURB'),
                 )

    if kwarg.get('mode'):
        ret['attrs'].append(['TCA_FLOW_MODE', get_tca_mode(kwarg)])

    if kwarg.get('keys'):
        ret['attrs'].append(['TCA_FLOW_KEYS', get_tca_keys(kwarg)])

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class options(nla):
    nla_map = (('TCA_FLOW_UNSPEC', 'none'),
               ('TCA_FLOW_KEYS', 'tca_parse_keys'),
               ('TCA_FLOW_MODE', 'tca_parse_mode'),
               ('TCA_FLOW_BASECLASS', 'uint32'),
               ('TCA_FLOW_RSHIFT', 'uint32'),
               ('TCA_FLOW_ADDEND', 'uint32'),
               ('TCA_FLOW_MASK', 'uint32'),
               ('TCA_FLOW_XOR', 'uint32'),
               ('TCA_FLOW_DIVISOR', 'uint32'),
               ('TCA_FLOW_ACT', 'hex'),
               ('TCA_FLOW_POLICE', 'hex'),
               ('TCA_FLOW_EMATCHES', 'hex'),
               ('TCA_FLOW_PERTURB', 'uint32'),
               )

    class tca_parse_mode(nla):
        fields = (('flow_mode', 'I'),
                  )

        def decode(self):
            nla.decode(self)
            for key, value in tc_flow_modes.items():
                if self['flow_mode'] == value:
                    self['flow_mode'] = key
                    break

        def encode(self):
            self['flow_mode'] = self['value']
            nla.encode(self)

    class tca_parse_keys(nla):
        fields = (('flow_keys', 'I'),
                  )

        def decode(self):
            nla.decode(self)

            keys = ''
            for key, value in tc_flow_keys.items():
                if value & self['flow_keys']:
                    keys = '{0},{1}'.format(keys, key)

            self['flow_keys'] = keys.strip(',')

        def encode(self):
            self['flow_keys'] = self['value']
            nla.encode(self)
