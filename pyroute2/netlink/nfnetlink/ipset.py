from pyroute2.netlink.nfnetlink import nfgen_msg


IPSET_MAXNAMELEN = 32

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


class ipset_msg(nfgen_msg):
    nla_map = (('IPSET_ATTR_UNSPEC', 'none'),
               ('IPSET_ATTR_PROTOCOL', 'uint8'),
               ('IPSET_ATTR_SETNAME', 'asciiz'),
               ('IPSET_ATTR_TYPENAME', 'asciiz'),
               ('IPSET_ATTR_REVISION', 'uint8'),
               ('IPSET_ATTR_FAMILY', 'uint8'),
               ('IPSET_ATTR_FLAGS', 'hex'),
               ('IPSET_ATTR_DATA', 'hex'),
               ('IPSET_ATTR_ADT', 'hex'),
               ('IPSET_ATTR_LINENO', 'hex'),
               ('IPSET_ATTR_PROTOCOL_MIN', 'hex'))
