import struct
from pyroute2.netlink import nla
from pyroute2.netlink import nlmsg

# see em_ipset.c
IPSET_DIM = {
    'IPSET_DIM_ZERO': 0,
    'IPSET_DIM_ONE': 1,
    'IPSET_DIM_TWO': 2,
    'IPSET_DIM_THREE': 3,
    'IPSET_DIM_MAX': 6,
}

TCF_EM_REL_END = 0
TCF_EM_REL_AND = 1
TCF_EM_REL_OR = 2
TCF_EM_REL_MASK = 3
TCF_EM_INVERT_MASK = 4
TCF_EM_SIMPLE_PAYLOAD_MASK = 6
TCF_EM_REL_VALID = lambda x : x & TCF_EM_REL_MASK != TCF_EM_REL_MASK
TCF_EM_INVERT = lambda x : x & TCF_EM_INVERT_MASK == TCF_EM_INVERT_MASK
TCF_EM_SIMPLE_PAYLOAD = lambda x : x & TCF_EM_SIMPLE_PAYLOAD_MASK == TCF_EM_SIMPLE_PAYLOAD_MASK

TCF_IPSET_MODE_DST = 0
TCF_IPSET_MODE_SRC = 2

def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (
        ('matchid', 'TCF_EM_MATCHID'),
        ('kind', 'TCF_EM_KIND'),
        ('flags', 'TCF_EM_FLAGS'),
        ('pad', 'TCF_EM_PAD'),
        ('opt', 'TCF_IP_SET_OPT')
    )

    if 'flags' in kwarg:
        flags = kwarg['flags']
        if not TCF_EM_REL_VALID(flags):
            raise Exception('Invalid relation flag')


    opt = kwarg['opt']
    format = 'HBB'

    # Python struct hack because HBBI = 10 but HIBB = 8, Yay!
    while len(opt) < struct.calcsize(format):
        opt = opt + '\x00'

    # See xt_set.h
    res = struct.unpack(format, opt)
    ip_set_index = res[0]
    ip_set_flags = res[1]
    ip_set_mode = res[2]


    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


def set_parameters(kwarg):
    ret = {'attrs': []}

    ip_set_name = kwarg['match'][0]['name']
    ip_set_mode = kwarg['match'][0]['src']

    # Translate IP set name to IP set index
    ip_set_index = 3 #Cheater!

    # Translate IP set mode
    if ip_set_mode == 'dst':
        ip_set_mode = 0
    elif ip_set_mode == 'src':
        ip_set_mode = 2
    else:
        raise Exception('Unknown IP set mode "{0}"'.format(ip_set_mode))

    # Translate current relation
    ip_set_relation = TCF_EM_REL_END #Cheater!

    # Prepare value buffer


class options(nla):
    nla_map = (('TCF_IP_SET_OPT', 'parse_ip_set_options'),
               )


    class parse_ip_set_options(nlmsg):
        fields = (('ip_set_index', 'H'),
                  ('ip_set_flags', 'B'),
                  ('ip_set_mode', 'B'),
                  )
