'''DHCP client state machine helpers.'''

import functools
from enum import IntEnum, auto
from logging import getLogger
from typing import Any, Awaitable, Callable, Final

LOG = getLogger(__name__)


class State(IntEnum):
    '''DHCP client states.

    see
    http://www.tcpipguide.com/free/t_DHCPGeneralOperationandClientFiniteStateMachine.htm
    '''

    OFF = 0
    INIT = auto()
    INIT_REBOOT = auto()
    REBOOTING = auto()
    REQUESTING = auto()
    SELECTING = auto()
    BOUND = auto()
    RENEWING = auto()
    REBINDING = auto()


# allowed transitions between states
TRANSITIONS: Final[dict[State, set[State]]] = {
    State.OFF: {State.INIT, State.INIT_REBOOT},
    State.INIT_REBOOT: {State.REBOOTING},
    State.REBOOTING: {State.INIT, State.BOUND},
    State.INIT: {State.SELECTING},
    State.SELECTING: {State.REQUESTING, State.INIT},
    State.REQUESTING: {State.BOUND, State.INIT},
    State.BOUND: {State.INIT, State.RENEWING, State.REBINDING},
    State.RENEWING: {State.BOUND, State.INIT, State.REBINDING},
    State.REBINDING: {State.BOUND, State.INIT},
}


def state_guard(
    *states: State,
) -> Callable[
    [Callable[..., Awaitable[None]]], Callable[..., Awaitable[None]]
]:
    '''Decorator that prevents a method from running

    if the associated instance is not in one of the given States.'''

    def decorator(
        meth: Callable[..., Awaitable[None]],
    ) -> Callable[..., Awaitable[None]]:
        @functools.wraps(meth)
        async def wrapper(self, *args: Any, **kwargs: Any) -> None:
            if self.state not in states:
                LOG.debug(
                    'Ignoring call to %r in %s state',
                    meth.__name__,
                    self.state.name,
                )
                return
            await meth(self, *args, **kwargs)

        return wrapper

    return decorator
