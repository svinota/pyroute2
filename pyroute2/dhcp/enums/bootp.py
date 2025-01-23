from enum import IntEnum, IntFlag


class MessageType(IntEnum):
    BOOTREQUEST = 1  # Client to server
    BOOTREPLY = 2  # Server to client


class HardwareType(IntEnum):
    ETHERNET = 1  # Ethernet (10Mb)
    EXPERIMENTAL_ETHERNET = 2
    AMATEUR_RADIO = 3
    TOKEN_RING = 4
    FDDI = 8
    ATM = 19
    WIRELESS_IEEE_802_11 = 20


class Flag(IntFlag):
    UNICAST = 0x0000  # Unicast response requested
    BROADCAST = 0x8000  # Broadcast response requested


class Option(IntEnum):
    PAD = 0  # Padding (no operation)
    SUBNET_MASK = 1  # Subnet mask
    ROUTER = 3  # Router address
    DNS_SERVER = 6  # Domain name server
    HOSTNAME = 12  # Hostname
    BOOTFILE_SIZE = 13  # Boot file size
    DOMAIN_NAME = 15  # Domain name
    IP_ADDRESS_LEASE_TIME = 51  # DHCP lease time
    MESSAGE_TYPE = 53  # DHCP message type (extended from BOOTP)
    SERVER_IDENTIFIER = 54  # DHCP server identifier
    END = 255  # End of options
