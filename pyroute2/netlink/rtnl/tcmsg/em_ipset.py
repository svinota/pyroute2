import struct
from pyroute2.netlink import nla
from pyroute2.netlink import nlmsg
#from pyroute2 import IPSet

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


def set_parameters(kwarg):
    ret = {'attrs': []}

    if 'name' in kwarg['match'][0] and 'index' in kwarg['match'][0]:
        raise Exception('You cannot use name and index to select an IPSet')

    if 'name' in kwarg['match'][0]:
        name = kwarg['match'][0]['name']
        raise Exception('IPSet match with name is not implemented!')
        #with IPSet() as ips:
        #    if ips.headers(name).get_attr('IPSET_ATTR_INDEX') is None:
        #        raise Exception('Your kernel is too old! Use index instead of name')
        #    else:
        #        ip_set_index = None # IMPLEMENT ME

    if 'index' in kwarg['match'][0]:
        ip_set_index = int(kwarg['match'][0]['index'])

    # Translate IP set mode
    ip_set_mode = kwarg['match'][0]['mode']
    if ip_set_mode == 'dst':
        ip_set_flags = TCF_IPSET_MODE_DST
    elif ip_set_mode == 'src':
        ip_set_flags = TCF_IPSET_MODE_SRC
    else:
        raise Exception('Unknown IP set mode "{0}"'.format(ip_set_mode))

    # TODO: inverse flag might also be set in ip_set_flags as it is referenced in the xt_set.h file

    # Force IPSet dimension to 1
    ip_set_dim = IPSET_DIM['IPSET_DIM_ONE']

    # FIXME: return a static integer for the moment...
    data = struct.pack('HBB', ip_set_index, ip_set_dim, ip_set_flags)
    ret['attrs'].append({'opt': struct.unpack('I', data)[0]})

    # Build match flags, currently force to only one relation in expression
    match_flags = TCF_EM_REL_END

    # Check for inverse flag
    if 'inverse' in kwarg['match'][0]:
        inverse = kwarg['match'][0]['inverse']
        if inverse:
            match_flags |= TCF_EM_INVERSE_MASK
    ret['attrs'].append({'flags': match_flags})

    return ret


class options(nla):
    nla_map = (('TCF_IP_SET_OPT', 'parse_ip_set_options'),
               )

    def encode(self):
        print 'Coucou from em_ipset'
        print self


    class parse_ip_set_options(nlmsg):
        fields = (('ip_set_index', 'H'),
                  ('ip_set_dim', 'B'),
                  ('ip_set_flags', 'B'),
                  )
