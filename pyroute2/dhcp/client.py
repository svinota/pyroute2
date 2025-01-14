import asyncio
from logging import getLogger
from typing import ClassVar, Iterable

from pyroute2.dhcp import fsm, messages
from pyroute2.dhcp.constants import dhcp
from pyroute2.dhcp.dhcp4msg import dhcp4msg
from pyroute2.dhcp.dhcp4socket import AsyncDHCP4Socket
from pyroute2.dhcp.hooks import Hook
from pyroute2.dhcp.leases import JSONFileLease, Lease
from pyroute2.dhcp.timers import Timers

LOG = getLogger(__name__)


class AsyncDHCPClient:
    '''A simple async DHCP client based on pyroute2.'''

    DEFAULT_PARAMETERS: ClassVar[tuple[dhcp.Parameter]] = [
        dhcp.Parameter.SUBNET_MASK,
        dhcp.Parameter.ROUTER,
        dhcp.Parameter.DOMAIN_NAME_SERVER,
        dhcp.Parameter.DOMAIN_NAME,
    ]

    def __init__(
        self,
        interface: str,
        lease_type: type[Lease] = JSONFileLease,
        hooks: Iterable[Hook] = (),
        requested_parameters: Iterable[dhcp.Parameter] = (),
    ):
        self.interface = interface
        self.lease_type = lease_type
        self.hooks = hooks
        self._sock: AsyncDHCP4Socket = AsyncDHCP4Socket(self.interface)
        self._state: fsm.fsm.State | None = None
        self._lease: Lease | None = None
        self.requested_parameters = list(
            requested_parameters
            if requested_parameters
            else self.DEFAULT_PARAMETERS
        )
        self._stopped = asyncio.Event()
        self._sendq: asyncio.Queue[dhcp4msg | None] = asyncio.Queue()
        self._send_task: asyncio.Task | None = None
        self.bound = asyncio.Event()
        self.timers = Timers()

    async def _renew(self):
        '''Called when the renewal timer, as defined in the lease, expires.'''
        assert self.lease, 'cannot renew without an existing lease'
        LOG.info('Renewal timer expired')
        # TODO: send only to server that gave us the current lease
        self.timers._reset_timer('renewal')
        await self.transition(
            to=fsm.State.RENEWING,
            send=messages.request(
                requested_ip=self.lease.ip,
                server_id=self.lease.server_id,
                parameter_list=self.requested_parameters,
            ),
        )

    async def _rebind(self):
        assert self.lease, 'cannot rebind without an existing lease'
        LOG.info('Rebinding timer expired')
        self.timers._reset_timer('rebinding')
        await self.transition(
            to=fsm.State.REBINDING,
            send=messages.request(
                requested_ip=self.lease.ip,
                server_id=self.lease.server_id,
                parameter_list=self.requested_parameters,
            ),
        )

    async def _expire_lease(self):
        LOG.info('Lease expired')
        self.timers._reset_timer('expiration')
        self.state = fsm.State.INIT
        # FIXME: call hooks in a non blocking way (maybe call_soon ?)
        for i in self.hooks:
            await i.unbound(self.lease)
        self._lease = None
        await self.bootstrap()

    @property
    def lease(self) -> Lease | None:
        return self._lease

    @lease.setter
    def lease(self, value: Lease):
        '''Set a fresh lease; only call this when a server grants one.'''
        self._lease = value
        self.timers.arm(
            lease=self.lease,
            renewal=self._renew,
            rebinding=self._rebind,
            expiration=self._expire_lease,
        )
        self.lease.dump()

    @property
    def state(self) -> fsm.State | None:
        return self._state

    @state.setter
    def state(self, value: fsm.State | None):
        if value and self._state and value not in fsm.TRANSITIONS[self._state]:
            raise ValueError(
                f'Cannot transition from {self._state} to {value}'
            )
        LOG.info('%s -> %s', self.state, value)
        self._state = value

    async def _run(self):
        packet_to_send: dhcp4msg | None = None
        # TODO: refactor, this is even more awkward than select()
        while True:
            wait_for_stopped = asyncio.Task(
                self._stopped.wait(), name='wait until stopped'
            )
            wait_for_received_packet = asyncio.Task(
                self._sock.get(), name='wait for received packet'
            )
            wait_for_packet_to_send = asyncio.Task(
                self._sendq.get(), name='wait for packet to send'
            )
            tasks = (
                wait_for_stopped,
                wait_for_received_packet,
                wait_for_packet_to_send,
            )
            done, pending = await asyncio.wait(
                tasks,
                timeout=5,  # TODO interval
                return_when=asyncio.FIRST_COMPLETED,
            )
            for i in pending:
                i.cancel()

            if wait_for_packet_to_send in done:
                packet_to_send = wait_for_packet_to_send.result()

            if wait_for_received_packet in done:
                received_packet = wait_for_received_packet.result()
                msg_type = dhcp.MessageType(
                    received_packet['options']['message_type']
                )
                LOG.info('Received %s', msg_type.name)
                if received_packet.get('xid') != self.xid:
                    LOG.error('Missing or wrong xid, discarding')
                else:
                    handler_name = f'{msg_type.name.lower()}_received'
                    handler = getattr(self, handler_name, None)
                    if not handler:
                        LOG.debug('%r messages are not handled', msg_type.name)
                    else:
                        if await handler(received_packet):
                            packet_to_send = None

            if packet_to_send:
                packet_to_send['xid'] = self.xid
                LOG.debug(
                    'Sending %s',
                    packet_to_send['options']['message_type'].name,
                )
                await self._sock.put(packet_to_send)

            if wait_for_stopped in done and wait_for_stopped.result() is True:
                return

    async def transition(self, to: fsm.State, send: dhcp4msg | None = None):
        self.state = to
        await self._sendq.put(send)

    @fsm.state_guard(fsm.State.INIT, fsm.State.INIT_REBOOT)
    async def bootstrap(self):
        '''Send a `DISCOVER` or a `REQUEST`,

        depending on whether we're initializing or rebooting.
        '''
        match self.state:
            case fsm.State.INIT:
                # send discover
                await self.transition(
                    to=fsm.State.SELECTING,
                    send=messages.discover(
                        parameter_list=self.requested_parameters
                    ),
                )
            case fsm.State.INIT_REBOOT:
                assert self.lease, 'cannot init_reboot without a lease'
                # send request for lease
                await self.transition(
                    to=fsm.State.REBOOTING,
                    send=messages.request(
                        requested_ip=self.lease.ip,
                        server_id=self.lease.server_id,
                        parameter_list=self.requested_parameters,
                    ),
                )

    @fsm.state_guard(
        fsm.State.REQUESTING,
        fsm.State.REBOOTING,
        fsm.State.REBINDING,
        fsm.State.RENEWING,
    )
    async def ack_received(self, pkt: dhcp4msg):
        self.lease = self.lease_type(ack=pkt, interface=self.interface)
        LOG.info(
            'Got lease for %s from %s', self.lease.ip, self.lease.server_id
        )
        await self.transition(to=fsm.State.BOUND)
        self.bound.set()
        # FIXME: call hooks in a non blocking way (maybe call_soon ?)
        for i in self.hooks:
            await i.bound(self.lease)
        return True

    @fsm.state_guard(fsm.State.SELECTING)
    async def offer_received(self, pkt: dhcp4msg):
        await self.transition(
            to=fsm.State.REQUESTING,
            send=messages.request(
                requested_ip=pkt['yiaddr'],
                server_id=pkt['options']['server_id'],
                parameter_list=self.requested_parameters,
            ),
        )
        return True

    async def __aenter__(self):
        self._lease = self.lease_type.load(self.interface)
        if self.lease:
            # TODO check lease is not expired
            self.state = fsm.State.INIT_REBOOT
        else:
            LOG.debug('No current lease')
            self.state = fsm.State.INIT
        await self._sock.__aenter__()
        self._send_task = asyncio.Task(self._run())
        self.xid = self._sock.xid_pool.alloc()
        return self

    async def __aexit__(self, *_):
        self.timers.cancel()
        if self.lease:
            await self._sendq.put(
                messages.release(
                    requested_ip=self.lease.ip, server_id=self.lease.server_id
                )
            )
        self._stopped.set()
        await self._send_task
        await self._sock.__aexit__()
        self.xid = None
        self.state = None
        self.bound.clear()
