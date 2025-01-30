import asyncio
import random
from dataclasses import dataclass, field
from logging import getLogger
from math import floor
from time import time
from typing import Callable, DefaultDict, Iterable, Iterator, Optional, Union

from pyroute2.dhcp import fsm, messages
from pyroute2.dhcp.dhcp4socket import AsyncDHCP4Socket
from pyroute2.dhcp.enums import dhcp
from pyroute2.dhcp.hooks import Hook, Trigger, run_hooks
from pyroute2.dhcp.leases import JSONFileLease, Lease
from pyroute2.dhcp.timers import LeaseTimers
from pyroute2.dhcp.xids import Xid

LOG = getLogger(__name__)


# TODO: maybe move retransmission stuff to its own file
Retransmission = Callable[[], Union[Iterator[int], Iterator[float]]]


def randomized_increasing_backoff(
    wait_first: float = 4.0, wait_max: float = 32.0, factor: float = 2.0
):
    '''Yields seconds to wait until the next retry, forever.'''
    delay = wait_first
    while True:
        yield delay
        if delay <= wait_max:
            delay = min(random.uniform(delay, delay * factor), wait_max)


@dataclass
class ClientConfig:
    '''Avoids heaps of __init__ args & variables in the DHCP client.'''

    interface: str
    lease_type: type[Lease] = JSONFileLease
    hooks: Iterable[Hook] = ()
    requested_parameters: Iterable[dhcp.Parameter] = (
        dhcp.Parameter.SUBNET_MASK,
        dhcp.Parameter.ROUTER,
        dhcp.Parameter.NAME_SERVER,
        dhcp.Parameter.DOMAIN_NAME,
        dhcp.Parameter.LEASE_TIME,
        dhcp.Parameter.RENEWAL_TIME,
        dhcp.Parameter.REBINDING_TIME,
    )
    timeouts: dict[fsm.State, int] = field(
        default_factory=lambda: {
            # No use staying too long in REBOOTING state if nobody is answering
            fsm.State.REBOOTING: 10,
            # When we get an OFFER, how long should we wait for an ACK ?
            fsm.State.REQUESTING: 30,
        }
    )
    # FIXME: we send too many retries according to the RFC
    # In both RENEWING and REBINDING states, if the client receives no
    # response to its DHCPREQUEST message, the client SHOULD wait one-half
    # of the remaining time until T2 (in RENEWING state) and one-half of
    # the remaining lease time (in REBINDING state), down to a minimum of
    # 60 seconds, before retransmitting the DHCPREQUEST message.
    retransmission: Retransmission = randomized_increasing_backoff


class AsyncDHCPClient:
    '''A simple async DHCP client based on pyroute2.'''

    def __init__(self, config: ClientConfig):
        self.config = config
        # The raw socket used to send and receive packets
        self._sock: AsyncDHCP4Socket = AsyncDHCP4Socket(self.config.interface)
        # Current client state
        self._state: fsm.State = fsm.State.OFF
        # Current lease, read from persistent storage or sent by a server
        self._lease: Optional[Lease] = None
        # dhcp messages put in this queue are sent by _send_forever
        self._sendq: asyncio.Queue[Optional[messages.SentDHCPMessage]] = (
            asyncio.Queue()
        )
        # Handle to run _send_forever for the context manager's lifetime
        self._sender_task: Optional[asyncio.Task] = None
        # Handle to run _recv_forever for the context manager's lifetime
        self._receiver_task: Optional[asyncio.Task] = None
        # Timers to run callbacks on lease timeouts expiration
        self.lease_timers = LeaseTimers()
        # Calls reset() after a timeout in some states to avoid getting stuck
        self._state_watchdog: asyncio.Task | None = None
        # Allows to easily track the state when running the client from python
        self._states: DefaultDict[fsm.State, asyncio.Event] = DefaultDict(
            asyncio.Event
        )
        # Used to compute lease times, taking into account the request time
        self.last_state_change: float = time()
        self.xid: Xid = Xid()

    # 'public api'

    async def wait_for_state(
        self, state: fsm.State, timeout: Optional[float] = None
    ) -> None:
        '''Waits until the client is in the target state.'''
        try:
            await asyncio.wait_for(self._states[state].wait(), timeout=timeout)
        except TimeoutError as err:
            raise TimeoutError(
                f'Timed out waiting for the {state.name} state. '
                f'Current state: {self.state.name}'
            ) from err

    @fsm.state_guard(fsm.State.INIT, fsm.State.INIT_REBOOT)
    async def bootstrap(self):
        '''Send a `DISCOVER` or a `REQUEST`,

        depending on whether we're initializing or rebooting.

        Use this to get a lease when running the client from Python code.
        '''
        if self.state is fsm.State.INIT:
            # send discover
            await self.transition(
                to=fsm.State.SELECTING,
                send=messages.discover(
                    parameter_list=self.config.requested_parameters
                ),
            )
        elif self.state is fsm.State.INIT_REBOOT:
            assert self.lease, 'cannot init_reboot without a lease'
            # send request for lease
            await self.transition(
                to=fsm.State.REBOOTING,
                send=messages.request_for_lease(
                    parameter_list=self.config.requested_parameters,
                    lease=self.lease,
                    state=fsm.State.REBOOTING,
                ),
            )
        # the decorator prevents the needs for an else

    # properties

    @property
    def lease(self) -> Optional[Lease]:
        '''The current lease, if we have one.'''
        return self._lease

    @lease.setter
    def lease(self, value: Lease):
        '''Set a fresh lease; only call this when a server grants one.'''

        self._lease = value
        self.lease_timers.arm(
            lease=self._lease,
            renewal=self._renew,
            rebinding=self._rebind,
            expiration=self._expire_lease,
        )
        self._lease.dump()

    @property
    def state(self) -> fsm.State:
        '''The current client state.'''
        return self._state

    @state.setter
    def state(self, value: fsm.State):
        '''Check the client can transition to the state, and set it.'''
        old_state = self.state
        if value and old_state and value not in fsm.TRANSITIONS[old_state]:
            raise ValueError(
                f'Cannot transition from {self._state.name} to {value.name}'
            )
        LOG.info('%s -> %s', old_state.name, value.name)
        if self._state_watchdog:
            self._state_watchdog.cancel()
            self._state_watchdog = None
        if old_state in self._states:
            self._states[old_state].clear()
        self._state = value
        self.last_state_change = time()
        self._states[value].set()
        if value and (state_timeout := self.config.timeouts.get(value)):
            self._state_watchdog = asyncio.Task(
                self.reset(delay=state_timeout)
            )

    # Timer callbacks

    async def _renew(self):
        '''Called when the renewal time defined in the lease expires.'''
        assert self.lease, 'cannot renew without an existing lease'
        LOG.info('Renewal timer expired')
        self.lease_timers._reset_timer('renewal')  # FIXME should be automatic
        await self.transition(
            to=fsm.State.RENEWING,
            send=messages.request_for_lease(
                parameter_list=self.config.requested_parameters,
                lease=self.lease,
                state=fsm.State.RENEWING,
            ),
        )

    async def _rebind(self):
        '''Called when the rebinding time defined in the lease expires.'''
        assert self.lease, 'cannot rebind without an existing lease'
        LOG.info('Rebinding timer expired')
        self.lease_timers._reset_timer('rebinding')
        await self.transition(
            to=fsm.State.REBINDING,
            send=messages.request_for_lease(
                parameter_list=self.config.requested_parameters,
                lease=self.lease,
                state=fsm.State.REBINDING,
            ),
        )

    async def _expire_lease(self):
        '''Called when the expiration time defined in the lease expires.'''
        LOG.info('Lease expired')
        self.lease_timers._reset_timer('expiration')
        await run_hooks(
            hooks=self.config.hooks, lease=self.lease, trigger=Trigger.EXPIRED
        )
        await self.reset()

    async def reset(self, delay: float = 0.0):
        if delay:
            await asyncio.sleep(delay=delay)
            LOG.warning('Resetting after %.1f seconds', delay)
        await self.transition(to=fsm.State.INIT)
        # Reset lease & timers and start again
        self._lease = None
        self.lease_timers.cancel()
        self.xid: Xid = Xid()
        await self.bootstrap()

    # DHCP packet sending & receving coroutines

    async def _send_forever(self) -> None:
        '''Send packets from _sendq until the client stops.'''
        msg_to_send: Optional[messages.SentDHCPMessage] = None
        # Called to get the interval value below
        interval_factory: Optional[Union[Iterator[int], Iterator[float]]] = (
            None
        )
        # How long to sleep before retrying
        interval: Union[int, float] = 1

        wait_til_off = asyncio.Task(self.wait_for_state(fsm.State.OFF))
        while not (wait_til_off.done() and self._sendq.empty()):

            if interval_factory:
                interval = next(interval_factory)
            else:
                interval = 9999999

            wait_for_msg_to_send = asyncio.Task(
                self._sendq.get(), name='wait for packet to send'
            )
            if msg_to_send:
                LOG.debug('%.1f seconds until retransmission', interval)
            done, pending = await asyncio.wait(
                (wait_til_off, wait_for_msg_to_send),
                return_when=asyncio.FIRST_COMPLETED,
                timeout=interval,
            )
            if wait_for_msg_to_send in done:
                if msg_to_send := wait_for_msg_to_send.result():
                    # There is a new message to send, reset the interval
                    interval_factory = self.config.retransmission()
                else:
                    # No need to retry anything
                    interval_factory = None
            elif wait_for_msg_to_send in pending:
                wait_for_msg_to_send.cancel()
            if msg_to_send:
                # Set secs to the time elapsed since the last state change
                # (max 16 bits)
                msg_to_send.dhcp['secs'] = min(
                    floor(time() - self.last_state_change), 0xFFFF
                )
                msg_to_send.dhcp['xid'] = self.xid.for_state(self.state)
                LOG.info('Sending %s', msg_to_send)
                await self._sock.put(msg_to_send)

    async def _recv_forever(self) -> None:
        '''Receive & process DHCP packets until the client stops.

        The incoming packet's xid is checked against the client's.
        Then, the relevant handler ({type}_received) is called.
        '''

        wait_til_off = asyncio.Task(self.wait_for_state(fsm.State.OFF))

        while not wait_til_off.done():
            wait_for_received_packet = asyncio.Task(
                coro=self._sock.get(),
                name=f'wait for DHCP packet on {self.config.interface}',
            )
            done, pending = await asyncio.wait(
                (wait_til_off, wait_for_received_packet),
                return_when=asyncio.FIRST_COMPLETED,
            )

            if wait_for_received_packet in done:
                received_packet = wait_for_received_packet.result()
                msg_type = dhcp.MessageType(
                    received_packet.dhcp['options']['message_type']
                )
                LOG.info('Received %s', received_packet)
                if not self.xid.matches(received_packet.xid):
                    LOG.error(
                        'Incorrect xid %s (expected %sX), discarding',
                        received_packet.xid,
                        hex(self.xid.random_part)[:-1],
                    )
                else:
                    handler_name = f'{msg_type.name.lower()}_received'
                    handler = getattr(self, handler_name, None)
                    if not handler:
                        LOG.debug('%r messages are not handled', msg_type.name)
                    else:
                        await handler(received_packet)

            elif wait_for_received_packet in pending:
                wait_for_received_packet.cancel()

    async def transition(
        self, to: fsm.State, send: Optional[messages.SentDHCPMessage] = None
    ):
        '''Change the client's state, and start sending a message repeatedly.

        If the message is None, any current message will stop being sent.
        '''
        self.state = to
        await self._sendq.put(send)

    # Callbacks for received DHCP messages

    @fsm.state_guard(
        fsm.State.REQUESTING,
        fsm.State.REBOOTING,
        fsm.State.REBINDING,
        fsm.State.RENEWING,
    )
    async def ack_received(self, msg: messages.ReceivedDHCPMessage):
        '''Called when an ACK is received.

        Stores the lease and puts the client in the BOUND state.
        '''
        # FIXME: according to the RFC:
        # When the client receives a DHCPACK from the server, the client
        # computes the lease expiration time as the sum of the time at which
        # the client sent the DHCPREQUEST message and the duration of the lease
        # in the DHCPACK message.
        self.lease = self.config.lease_type(
            ack=msg.dhcp,
            interface=self.config.interface,
            server_mac=msg.eth_src,
        )
        LOG.info(
            'Got lease for %s from %s', self.lease.ip, self.lease.server_id
        )
        await self.transition(to=fsm.State.BOUND)

        request_state = msg.xid.request_state

        if request_state in (fsm.State.REQUESTING, fsm.State.REBOOTING):
            trigger = Trigger.BOUND
        elif request_state == fsm.State.RENEWING:
            trigger = Trigger.RENEWED
        elif request_state == fsm.State.REBINDING:
            trigger = Trigger.REBOUND
        else:
            LOG.warning("Invalid request state %s in xid", request_state)
            return

        await run_hooks(
            hooks=self.config.hooks, lease=self.lease, trigger=trigger
        )

    @fsm.state_guard(
        fsm.State.REQUESTING,
        fsm.State.REBOOTING,
        fsm.State.RENEWING,
        fsm.State.REBINDING,
    )
    async def nak_received(self, msg: messages.ReceivedDHCPMessage):
        '''Called when a NAK is received.

        Resets the client and starts looking for a new IP.
        '''
        await self.reset()

    @fsm.state_guard(fsm.State.SELECTING)
    async def offer_received(self, msg: messages.ReceivedDHCPMessage):
        '''Called when an OFFER is received.

        Sends a REQUEST for the offered IP address.
        '''
        await self.transition(
            to=fsm.State.REQUESTING,
            send=messages.request_for_offer(
                parameter_list=self.config.requested_parameters, offer=msg
            ),
        )

    # Async context manager methods

    async def __aenter__(self):
        '''Set up the client so it's ready to obtain an IP.

        Tries to load a lease for the client's interface,
        opens the socket, starts the sender & receiver tasks
        and allocates a request ID.
        '''
        if loaded_lease := self.config.lease_type.load(self.config.interface):
            self._lease = loaded_lease
            self.state = fsm.State.INIT_REBOOT
        else:
            LOG.debug('No current lease')
            self.state = fsm.State.INIT
        await self._sock.__aenter__()

        self._receiver_task = asyncio.Task(
            self._recv_forever(),
            name=f'Listen for DHCP packets on {self.config.interface}',
        )
        self._sender_task = asyncio.Task(
            self._send_forever(),
            name=f'Send outgoing DHCP packets on {self.config.interface}',
        )
        return self

    async def __aexit__(self, *_):
        '''Shut down the client.

        If there's an active lease, send a RELEASE for it first.
        '''
        self.lease_timers.cancel()
        # FIXME: call hooks in a non blocking way (maybe call_soon ?)
        if self.lease:
            await run_hooks(
                hooks=self.config.hooks,
                lease=self.lease,
                trigger=Trigger.UNBOUND,
            )
            if not self.lease.expired:
                await self._sendq.put(messages.release(lease=self.lease))
        self.state = fsm.State.OFF
        await self._sender_task
        await self._receiver_task
        await self._sock.__aexit__()
        self.xid = None
