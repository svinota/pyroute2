
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla

## address attributes
#
# Important comment:
# IFA_ADDRESS is prefix address, rather than local interface address.
# It makes no difference for normally configured broadcast interfaces,
# but for point-to-point IFA_ADDRESS is DESTINATION address,
# local address is supplied in IFA_LOCAL attribute.
#


class ifaddrmsg(nlmsg):
    """
    IP address information

    struct ifaddrmsg {
       unsigned char ifa_family;    /* Address type */
       unsigned char ifa_prefixlen; /* Prefixlength of address */
       unsigned char ifa_flags;     /* Address flags */
       unsigned char ifa_scope;     /* Address scope */
       int           ifa_index;     /* Interface index */
    };

    """
    fmt = 'BBBBI'
    fields = ('family',
              'prefixlen',
              'flags',
              'scope',
              'index')

    nla_map = (('IFA_UNSPEC',  'hex'),
               ('IFA_ADDRESS', 'ipaddr'),
               ('IFA_LOCAL', 'ipaddr'),
               ('IFA_LABEL', 'asciiz'),
               ('IFA_BROADCAST', 'ipaddr'),
               ('IFA_ANYCAST', 'ipaddr'),
               ('IFA_CACHEINFO', 'cacheinfo'),
               ('IFA_MULTICAST', 'ipaddr'))

    class cacheinfo(nla):
        fmt = "I" * 4
        fields = ('ifa_prefered',
                  'ifa_valid',
                  'cstamp',
                  'tstamp')
