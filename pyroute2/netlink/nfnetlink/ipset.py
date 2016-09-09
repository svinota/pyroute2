from pyroute2.netlink import nla
from pyroute2.netlink import NLA_F_NESTED
from pyroute2.netlink import NLA_F_NET_BYTEORDER
from pyroute2.netlink.nfnetlink import nfgen_msg


IPSET_MAXNAMELEN = 32
IPSET_DEFAULT_MAXELEM = 65536

IPSET_CMD_NONE = 0
IPSET_CMD_PROTOCOL = 1  # Return protocol version
IPSET_CMD_CREATE = 2  # Create a new (empty) set
IPSET_CMD_DESTROY = 3  # Destroy a (empty) set
IPSET_CMD_FLUSH = 4  # Remove all elements from a set
IPSET_CMD_RENAME = 5  # Rename a set
IPSET_CMD_SWAP = 6  # Swap two sets
IPSET_CMD_LIST = 7  # List sets
IPSET_CMD_SAVE = 8  # Save sets
IPSET_CMD_ADD = 9  # Add an element to a set
IPSET_CMD_DEL = 10  # Delete an element from a set
IPSET_CMD_TEST = 11  # Test an element in a set
IPSET_CMD_HEADER = 12  # Get set header data only
IPSET_CMD_TYPE = 13  # 13: Get set type


IPSET_FLAG_WITH_COUNTERS = 1 << 3
IPSET_FLAG_WITH_COMMENT = 1 << 4
IPSET_FLAG_WITH_FORCEADD = 1 << 5
IPSET_FLAG_WITH_SKBINFO = 1 << 6


class ipset_msg(nfgen_msg):
    '''
    Since the support just begins to be developed,
    many attrs are still in `hex` format -- just to
    dump the content.
    '''
    nla_map = (('IPSET_ATTR_UNSPEC', 'none'),
               ('IPSET_ATTR_PROTOCOL', 'uint8'),
               ('IPSET_ATTR_SETNAME', 'asciiz'),
               ('IPSET_ATTR_TYPENAME', 'asciiz'),
               ('IPSET_ATTR_REVISION', 'uint8'),
               ('IPSET_ATTR_FAMILY', 'uint8'),
               ('IPSET_ATTR_FLAGS', 'hex'),
               ('IPSET_ATTR_DATA', 'cadt_data'),
               ('IPSET_ATTR_ADT', 'adt_data'),
               ('IPSET_ATTR_LINENO', 'hex'),
               ('IPSET_ATTR_PROTOCOL_MIN', 'hex'))

    class ipset_generic(nla):
        class ipset_ip(nla):
            nla_flags = NLA_F_NESTED
            nla_map = (('IPSET_ATTR_UNSPEC', 'none'),
                       ('IPSET_ATTR_IPADDR_IPV4', 'ip4addr',
                        NLA_F_NET_BYTEORDER),
                       ('IPSET_ATTR_IPADDR_IPV6', 'ip6addr',
                        NLA_F_NET_BYTEORDER))

    class cadt_data(ipset_generic):
        nla_flags = NLA_F_NESTED
        nla_map = ((0, 'IPSET_ATTR_UNSPEC', 'none'),
                   (1, 'IPSET_ATTR_IP', 'ipset_ip'),
                   (1, 'IPSET_ATTR_IP_FROM', 'ipset_ip'),
                   (2, 'IPSET_ATTR_IP_TO', 'ipset_ip'),
                   (3, 'IPSET_ATTR_CIDR', 'be8', NLA_F_NET_BYTEORDER),
                   (4, 'IPSET_ATTR_PORT', 'be16', NLA_F_NET_BYTEORDER),
                   (4, 'IPSET_ATTR_PORT_FROM', 'be16', NLA_F_NET_BYTEORDER),
                   (5, 'IPSET_ATTR_PORT_TO', 'be16', NLA_F_NET_BYTEORDER),
                   (6, 'IPSET_ATTR_TIMEOUT', 'be32', NLA_F_NET_BYTEORDER),
                   (7, 'IPSET_ATTR_PROTO', 'recursive'),
                   (8, 'IPSET_ATTR_CADT_FLAGS', 'be32', NLA_F_NET_BYTEORDER),
                   (9, 'IPSET_ATTR_CADT_LINENO', 'be32'),
                   (10, 'IPSET_ATTR_MARK', 'hex'),
                   (11, 'IPSET_ATTR_MARKMASK', 'hex'),
                   (17, 'IPSET_ATTR_GC', 'hex'),
                   (17, 'IPSET_ATTR_ETHER', 'l2addr'),
                   (18, 'IPSET_ATTR_HASHSIZE', 'be32', NLA_F_NET_BYTEORDER),
                   (19, 'IPSET_ATTR_MAXELEM', 'be32', NLA_F_NET_BYTEORDER),
                   (20, 'IPSET_ATTR_NETMASK', 'hex'),
                   (21, 'IPSET_ATTR_PROBES', 'hex'),
                   (22, 'IPSET_ATTR_RESIZE', 'hex'),
                   (23, 'IPSET_ATTR_SIZE', 'hex'),
                   (23, 'IPSET_ATTR_IFACE', 'asciiz'),
                   (24, 'IPSET_ATTR_BYTES', 'be64'),
                   (25, 'IPSET_ATTR_PACKETS', 'be64'),
                   (26, 'IPSET_ATTR_COMMENT', 'asciiz'),
                   (27, 'IPSET_ATTR_SKBMARK', 'hex'),
                   (28, 'IPSET_ATTR_SKBPRIO', 'be32'),
                   (29, 'IPSET_ATTR_SKBQUEUE', 'hex'))

    class adt_data(ipset_generic):
        nla_flags = NLA_F_NESTED
        nla_map = ((0, 'IPSET_ATTR_UNSPEC', 'none'),
                   (1, 'IPSET_ATTR_IP', 'ipset_ip'),
                   (1, 'IPSET_ATTR_IP_FROM', 'ipset_ip'),
                   (2, 'IPSET_ATTR_IP_TO', 'ipset_ip'),
                   (3, 'IPSET_ATTR_CIDR', 'be8', NLA_F_NET_BYTEORDER),
                   (4, 'IPSET_ATTR_PORT', 'be16', NLA_F_NET_BYTEORDER),
                   (4, 'IPSET_ATTR_PORT_FROM', 'be16', NLA_F_NET_BYTEORDER),
                   (5, 'IPSET_ATTR_PORT_TO', 'be16', NLA_F_NET_BYTEORDER),
                   (6, 'IPSET_ATTR_TIMEOUT', 'be32', NLA_F_NET_BYTEORDER),
                   (7, 'IPSET_ATTR_PROTO', 'recursive'),
                   (8, 'IPSET_ATTR_CADT_FLAGS', 'be32', NLA_F_NET_BYTEORDER),
                   (9, 'IPSET_ATTR_CADT_LINENO', 'be32'),
                   (10, 'IPSET_ATTR_MARK', 'hex'),
                   (11, 'IPSET_ATTR_MARKMASK', 'hex'),
                   (17, 'IPSET_ATTR_ETHER', 'l2addr'),
                   (18, 'PSET_ATTR_NAME', 'hex'),
                   (19, 'IPSET_ATTR_NAMEREF', 'be32'),
                   (20, 'IPSET_ATTR_IP2', 'be32'),
                   (21, 'IPSET_ATTR_CIDR2', 'hex'),
                   (22, 'IPSET_ATTR_IP2_TO', 'hex'),
                   (23, 'IPSET_ATTR_IFACE', 'asciiz'),
                   (24, 'IPSET_ATTR_BYTES', 'be64'),
                   (25, 'IPSET_ATTR_PACKETS', 'be64'),
                   (26, 'IPSET_ATTR_COMMENT', 'asciiz'),
                   (27, 'IPSET_ATTR_SKBMARK', 'hex'),
                   (28, 'IPSET_ATTR_SKBPRIO', 'be32'),
                   (29, 'IPSET_ATTR_SKBQUEUE', 'hex'))
