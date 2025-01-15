'''Compatibility with older but supported Python versions'''

try:
    from enum import StrEnum
except ImportError:
    # StrEnum appeared in python 3.11

    from enum import Enum

    class StrEnum(str, Enum):
        '''Same as enum, but members are also strings.'''


__all__ = ('StrEnum',)
