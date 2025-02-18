from enum import IntEnum


class MessageType(IntEnum):
    '''DHCP message types, see RFC 2131 table 2.'''

    DISCOVER = 1
    OFFER = 2
    REQUEST = 3
    DECLINE = 4
    ACK = 5
    NAK = 6
    RELEASE = 7
    INFORM = 8


class Option(IntEnum):
    '''DHCP options and parameters.

    These constants are used for two purposes:

    - Requesting configuration values from the DHCP server.
      In this case, they're passed in the `PARAMETER_LIST` request option.
      Not all values are valid for parameter requests:
        - `PAD` is only used as padding when decoding server-sent options,
        - `PARAMETER_LIST` is only sent from client and cannot be requested,
        - `END` is used as a marker when decoding server-sent options.

    - Reading responses.
      `Option` numbers are used to parse DHCP options sent by the server.
      They are translated to their name by the client and stored in leases.
    '''

    PAD = 0
    SUBNET_MASK = 1
    TIME_OFFSET = 2
    ROUTER = 3
    TIME_SERVER = 4
    IEN_NAME_SERVER = 5  # prehistoric DNS
    # this should be DOMAIN_NAME_SERVER but it's often used & shorted this way
    NAME_SERVER = 6  # plain old DNS
    LOG_SERVER = 7
    COOKIE_SERVER = 8
    LPR_SERVER = 9
    IMPRESS_SERVER = 10
    RESOURCE_LOCATION_SERVER = 11
    HOST_NAME = 12
    BOOT_FILE_SIZE = 13
    MERIT_DUMP_FILE = 14
    DOMAIN_NAME = 15
    SWAP_SERVER = 16
    ROOT_PATH = 17
    EXTENSIONS_PATH = 18
    IP_FORWARDING = 19
    NON_LOCAL_SOURCE_ROUTING = 20
    POLICY_FILTER = 21
    MAX_DATAGRAM_REASSEMBLY = 22
    DEFAULT_TTL = 23
    PATH_MTU_AGING_TIMEOUT = 24
    PATH_MTU_PLATEAU_TABLE = 25
    INTERFACE_MTU = 26
    ALL_SUBNETS_LOCAL = 27
    BROADCAST_ADDRESS = 28
    PERFORM_MASK_DISCOVERY = 29
    MASK_SUPPLIER = 30
    PERFORM_ROUTER_DISCOVERY = 31
    ROUTER_SOLICITATION_ADDRESS = 32
    STATIC_ROUTE = 33
    TRAILER_ENCAPSULATION = 34
    ARP_CACHE_TIMEOUT = 35
    ETHERNET_ENCAPSULATION = 36
    TCP_DEFAULT_TTL = 37
    TCP_KEEPALIVE_INTERVAL = 38
    TCP_KEEPALIVE_GARBAGE = 39
    NIS_DOMAIN = 40
    NIS_SERVERS = 41
    NTP_SERVERS = 42
    VENDOR_SPECIFIC_INFORMATION = 43
    NETBIOS_NAME_SERVER = 44
    NETBIOS_DDG_SERVER = 45
    NETBIOS_NODE_TYPE = 46
    NETBIOS_SCOPE = 47
    X_WINDOW_FONT_SERVER = 48
    X_WINDOW_DISPLAY_MANAGER = 49
    REQUESTED_IP = 50
    LEASE_TIME = 51
    OPTION_OVERLOAD = 52
    MESSAGE_TYPE = 53
    SERVER_ID = 54
    PARAMETER_LIST = 55
    MESSAGE = 56
    MAX_MSG_SIZE = 57
    RENEWAL_TIME = 58
    REBINDING_TIME = 59
    VENDOR_ID = 60
    CLIENT_ID = 61
    NETWARE_IP_DOMAIN = 62
    NETWARE_IP_OPTION = 63
    NIS_PLUS_DOMAIN = 64
    NIS_PLUS_SERVERS = 65
    TFTP_SERVER_NAME = 66
    BOOTFILE_NAME = 67
    MOBILE_IP_HOME_AGENT = 68
    SMTP_SERVER = 69
    POP3_SERVER = 70
    NNTP_SERVER = 71
    DEFAULT_WWW_SERVER = 72
    DEFAULT_FINGER_SERVER = 73
    DEFAULT_IRC_SERVER = 74
    STREETTALK_SERVER = 75
    STDA_SERVER = 76
    USER_CLASS_INFORMATION = 77
    SLP_DIRECTORY_AGENT = 78
    SLP_SERVICE_SCOPE = 79
    RAPID_COMMIT = 80
    CLIENT_FQDN = 81
    RELAY_AGENT_INFORMATION = 82
    INTERNET_STORAGE_NAME_SERVICE = 83
    NDS_SERVERS = 85
    NDS_TREE_NAME = 86
    NDS_CONTEXT = 87
    BCMCS_CONTROLLER_DOMAIN = 88
    CLIENT_SYSTEM_ARCHITECTURE_TYPE = 93
    CLIENT_NETWORK_INTERFACE_IDENTIFIER = 94
    LDAP_SERVERS = 95
    IPV6_ONLY_PREFERRED = 108
    DHCP_CAPTIVE_PORTAL = 114
    DOMAIN_SEARCH = 119
    CLASSLESS_STATIC_ROUTE = 121
    PRIVATE_CLASSIC_ROUTE_MS = 249
    PRIVATE_PROXY_AUTODISCOVERY = 252
    END = 255
