
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla

# address attributes
#
# Important comment:
# For IPv4, IFA_ADDRESS is a prefix address, not a local interface
# address. It makes no difference for normal interfaces, but
# for point-to-point ones IFA_ADDRESS means DESTINATION address,
# and the local address is supplied in IFA_LOCAL attribute.
#


class ifaddrmsg(nlmsg):
    '''
    IP address information

    struct ifaddrmsg {
       unsigned char ifa_family;    /* Address type */
       unsigned char ifa_prefixlen; /* Prefixlength of address */
       unsigned char ifa_flags;     /* Address flags */
       unsigned char ifa_scope;     /* Address scope */
       int           ifa_index;     /* Interface index */
    };

    '''
    fields = (('family', 'B'),
              ('prefixlen', 'B'),
              ('flags', 'B'),
              ('scope', 'B'),
              ('index', 'I'))

    nla_map = (('IFA_UNSPEC',  'hex'),
               ('IFA_ADDRESS', 'ipaddr'),
               ('IFA_LOCAL', 'ipaddr'),
               ('IFA_LABEL', 'asciiz'),
               ('IFA_BROADCAST', 'ipaddr'),
               ('IFA_ANYCAST', 'ipaddr'),
               ('IFA_CACHEINFO', 'cacheinfo'),
               ('IFA_MULTICAST', 'ipaddr'))

    class cacheinfo(nla):
        fields = (('ifa_prefered', 'I'),
                  ('ifa_valid', 'I'),
                  ('cstamp', 'I'),
                  ('tstamp', 'I'))
