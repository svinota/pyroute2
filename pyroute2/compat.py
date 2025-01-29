'''Compatibility with older but supported Python versions'''

try:
    from enum import EnumType, StrEnum  # noqa: F401
except ImportError:
    # StrEnum appeared in python 3.11
    # EnumMeta was renamed to EnumType
    from enum import Enum
    from enum import EnumMeta as EnumType  # noqa: F401

    class StrEnum(str, Enum):
        '''Same as enum, but members are also strings.'''


try:
    from socket import ETHERTYPE_IP
except ImportError:
    # ETHERTYPE_* are new in python 3.12
    ETHERTYPE_IP = 0x800


__all__ = ('StrEnum', 'ETHERTYPE_IP')
