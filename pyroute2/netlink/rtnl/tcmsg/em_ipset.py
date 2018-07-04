import struct
from pyroute2.netlink import nlmsg_base

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
TCF_EM_INVERSE_MASK = 4
TCF_EM_SIMPLE_PAYLOAD_MASK = 6
TCF_EM_REL_VALID = lambda x : x & TCF_EM_REL_MASK != TCF_EM_REL_MASK
TCF_EM_INVERSE = lambda x : x & TCF_EM_INVERSE_MASK == TCF_EM_INVERSE_MASK
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

        #if flags & TCF_EM_REL_MASK == TCF_EM_REL_END:
        #     print '\nEnd of IPset relation'
        #if flags & TCF_EM_REL_AND == TCF_EM_REL_AND:
        #     print '\nAND relation between IPsets'
        #if flags & TCF_EM_REL_OR == TCF_EM_REL_OR:
        #     print '\nOR relation between IPsets'
        #if TCF_EM_INVERSE(flags):
        #     print '\nCondition inverse for IPset'


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

    #print '\nIPset data:\nMode: {0}\nIndex: {1}\nFlags: {2}\n'.format(
            #ip_set_mode, ip_set_index, ip_set_flags)

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class data(nlmsg_base):
    fields = (('ip_set_index', 'H'),
              ('ip_set_dim', 'B'),
              ('ip_set_flags', 'B'),
              )


    def encode(self):
        self['ip_set_index'] = self['index']
        self['ip_set_dim'] = IPSET_DIM['IPSET_DIM_ONE']
        self['ip_set_flags'] = TCF_IPSET_MODE_SRC
        nlmsg_base.encode(self)
