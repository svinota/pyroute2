from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.common import tc_actions


# Packet types defined in if_packet.h
PACKET_HOST = 0
PACKET_BROADCAST = 1
PACKET_MULTICAST = 2
PACKET_OTHERHOST = 3


def convert_ptype(value):
    types = {'host': PACKET_HOST,
             'otherhost': PACKET_OTHERHOST,
             'broadcast': PACKET_BROADCAST,
             'multicast': PACKET_MULTICAST,
             }

    res = types.get(value.lower())
    if res is not None:
        return res
    raise ValueError('Invalid ptype specified! See tc-skbedit man '
                     'page for valid values.')


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (('priority', 'TCA_SKBEDIT_PRIORITY'),
                 ('queue', 'TCA_SKBEDIT_QUEUE_MAPPING'),
                 ('mark', 'TCA_SKBEDIT_MARK'),
                 ('ptype', 'TCA_SKBEDIT_PTYPE'),
                 ('mask', 'TCA_SKBEDIT_MASK'),
                 )

    # Assign TCA_SKBEDIT_PARMS first
    parms = {}
    parms['action'] = tc_actions['pipe']
    ret['attrs'].append(['TCA_SKBEDIT_PARMS', parms])

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            if k == 'ptype':
                r = convert_ptype(r)
            ret['attrs'].append([v, r])

    return ret


class options(nla):
    nla_map = (('TCA_SKBEDIT_UNSPEC', 'none'),
               ('TCA_SKBEDIT_TM', 'hex'),
               ('TCA_SKBEDIT_PARMS', 'tca_parse_parms'),
               ('TCA_SKBEDIT_PRIORITY', 'uint32'),
               ('TCA_SKBEDIT_QUEUE_MAPPING', 'uint16'),
               ('TCA_SKBEDIT_MARK', 'uint32'),
               ('TCA_SKBEDIT_PAD', 'hex'),
               ('TCA_SKBEDIT_PTYPE', 'uint16'),
               ('TCA_SKBEDIT_MASK', 'uint32'),
               ('TCA_SKBEDIT_FLAGS', 'uint64'),
               )

    class tca_parse_parms(nla):
        # As described in tc_mpls.h, it uses
        # generic TC action fields
        fields = (('index', 'I'),
                  ('capab', 'I'),
                  ('action', 'i'),
                  ('refcnt', 'i'),
                  ('bindcnt', 'i'),
                  )
