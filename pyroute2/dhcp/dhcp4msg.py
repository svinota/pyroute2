from socket import AF_INET, inet_ntop, inet_pton

from pyroute2.dhcp import dhcpmsg, option
from pyroute2.dhcp.enums.dhcp import Option


class dhcp4msg(dhcpmsg):
    #
    # https://www.ietf.org/rfc/rfc2131.txt
    #
    fields = (
        ('op', 'uint8', 1),  # request
        ('htype', 'uint8', 1),  # ethernet
        ('hlen', 'uint8', 6),  # ethernet addr len
        ('hops', 'uint8'),
        ('xid', 'be32'),
        ('secs', 'be16'),
        ('flags', 'be16'),
        ('ciaddr', 'ip4addr'),
        ('yiaddr', 'ip4addr'),
        ('siaddr', 'ip4addr'),
        ('giaddr', 'ip4addr'),
        ('chaddr', 'l2paddr'),
        ('sname', '64s'),
        ('file', '128s'),
        ('cookie', '4s', b'c\x82Sc'),
    )
    #
    # https://www.ietf.org/rfc/rfc2132.txt
    #
    options = (
        (Option.PAD, 'none'),
        (Option.SUBNET_MASK, 'ip4addr'),
        (Option.TIME_OFFSET, 'be32'),
        (Option.ROUTER, 'ip4list'),
        (Option.TIME_SERVER, 'ip4list'),
        (Option.NAME_SERVER, 'ip4list'),
        (Option.LOG_SERVER, 'ip4list'),
        (Option.COOKIE_SERVER, 'ip4list'),
        (Option.LPR_SERVER, 'ip4list'),
        (Option.HOST_NAME, 'string'),
        (Option.INTERFACE_MTU, 'be16'),
        (Option.BROADCAST_ADDRESS, 'ip4addr'),
        (Option.REQUESTED_IP, 'ip4addr'),
        (Option.LEASE_TIME, 'be32'),
        (Option.MESSAGE_TYPE, 'message_type'),
        (Option.SERVER_ID, 'ip4addr'),
        (Option.PARAMETER_LIST, 'array8'),
        (Option.MAX_MSG_SIZE, 'be16'),
        (Option.RENEWAL_TIME, 'be32'),
        (Option.REBINDING_TIME, 'be32'),
        (Option.VENDOR_ID, 'string'),
        (Option.CLIENT_ID, 'client_id'),
        (Option.END, 'none'),
    )

    class ip4addr(option):
        policy = {
            'format': '4s',
            'encode': lambda x: inet_pton(AF_INET, x),
            'decode': lambda x: inet_ntop(AF_INET, x),
        }

    class ip4list(option):
        policy = {
            'format': 'string',
            'encode': lambda x: ''.join([inet_pton(AF_INET, i) for i in x]),
            'decode': lambda x: [
                inet_ntop(AF_INET, x[i * 4 : i * 4 + 4])
                for i in range(len(x) // 4)
            ],
        }
