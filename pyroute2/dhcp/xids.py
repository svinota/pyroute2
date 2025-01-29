import random
from typing import Optional

from pyroute2.dhcp.fsm import State


class Xid:
    '''Transaction IDs used to identify responses to DHCP requests.

    We use the last nibble to store the state the message was sent in.
    '''
    def __init__(self, value: Optional[int] = None):
        if value is None:
            value = random.randint(0x00000010, 0xFFFFFFF0)
        else:
            assert value < 0xFFFFFFFF  # we have 32 bits
        self._value = value

    @property
    def random_part(self) -> int:
        '''The random part of the transaction id.'''
        return self._value & 0xFFFFFFF0

    @property
    def request_state(self) -> State | None:
        '''The state in which the request was sent.

        Since servers answer with the same transaction ID as the request,
        we can use this to know what client state does a response answer to.
        '''
        try:
            return State(self._value & 0xF)
        except ValueError:
            return None

    def for_state(self, state: State) -> 'Xid':
        '''A new Xid built from the random part + the state.'''
        return Xid(self.random_part | state)

    def __index__(self) -> int:
        '''Allows xids to be used as int.'''
        return self._value

    def matches(self, received_xid: 'Xid'):
        '''Loose match, whether the random part of both XIDs match.

        This can be used to check if a message is indeed in response
        to a request we sent.
        '''
        return self.random_part == received_xid.random_part

    def __eq__(self, value):
        return self._value == value

    def __repr__(self):
        return f"Xid({hex(self._value)})"