'''Hooks called by the DHCP client when bound, a leases expires, etc.'''

import errno
from enum import auto
from logging import getLogger
from typing import Awaitable, Callable, Iterable, NamedTuple

from pyroute2.compat import StrEnum
from pyroute2.dhcp.leases import Lease
from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.netlink.exceptions import NetlinkError

LOG = getLogger(__name__)


class Trigger(StrEnum):
    '''Events that can trigger hooks in the client.'''

    # The client has obtained a new lease
    BOUND = auto()
    # The client has voluntarily relinquished its lease
    UNBOUND = auto()
    # The client has renewed its lease after the renewal timer expired
    RENEWED = auto()
    # The client has rebound its leas after the rebinding timer expired
    REBOUND = auto()
    # The lease has expired (the client will restart the lease process)
    EXPIRED = auto()


# Signature for functions that can be passed to the hook decorator
HookFunc = Callable[[Lease], Awaitable[None]]


class Hook(NamedTuple):
    '''Stores a hook function and its triggers.

    Returned by the `hook()` decorator; no need to subclass or instantiate.
    '''

    func: HookFunc
    triggers: set[Trigger]

    async def __call__(self, lease: Lease) -> None:
        '''Call the hook function.'''
        await self.func(lease)

    @property
    def name(self) -> str:
        '''Shortcut for the function name.'''
        return self.func.__name__


async def run_hooks(hooks: Iterable[Hook], lease: Lease, trigger: Trigger):
    '''Called by the client to run the hooks registered for the given trigger.

    Exceptions are handled and printed, but don't prevent the other hooks from
    running.
    '''
    for i in filter(lambda y: trigger in y.triggers, hooks):
        try:
            # TODO: what if a hook takes forever ? should there be a timeout ?
            await i(lease)
        except Exception:
            LOG.exception("Hook %s failed", i.name)


def hook(*triggers: Trigger) -> Callable[[HookFunc], Hook]:
    '''Decorator for dhcp client hooks.

    A hook is an async function that takes a lease as its single argument.
    Hooks set in `ClientConfig.hooks` will be called in order by the client
    when one of the triggers passed to the decorator happens.

    For example::

        @hook(Trigger.RENEWED)
        async def lease_was_renewed(lease: Lease):
            print(lease.server_mac, 'renewed our lease !')

    The decorator returns a `Hook` instance, a utility class storing the hook
    function and its triggers.

    **Warning**: The hooks API might still change.
    '''

    def decorator(hook_func: HookFunc) -> Hook:
        return Hook(func=hook_func, triggers=set(triggers))

    return decorator


@hook(Trigger.BOUND)
async def configure_ip(lease: Lease):
    '''Add the IP allocated in the lease to its interface.

    Use the `remove_ip` hook in addition to this one for cleanup.
    The DHCP server must have set the subnet mask and broadcast address.
    '''
    LOG.info(
        'Adding %s/%s to %s', lease.ip, lease.subnet_mask, lease.interface
    )
    async with AsyncIPRoute() as ipr:
        await ipr.addr(
            'replace',
            index=await ipr.link_lookup(ifname=lease.interface),
            address=lease.ip,
            prefixlen=lease.subnet_mask,
            # FIXME: maybe make this optional
            broadcast=lease.broadcast_address,
        )


@hook(Trigger.UNBOUND, Trigger.EXPIRED)
async def remove_ip(lease: Lease):
    '''Remove the IP in the lease from its interface.'''
    LOG.info(
        'Removing %s/%s from %s', lease.ip, lease.subnet_mask, lease.interface
    )
    # FIXME: don't raise if someone removed the IP, just log something.
    async with AsyncIPRoute() as ipr:
        await ipr.addr(
            'del',
            index=await ipr.link_lookup(ifname=lease.interface),
            address=lease.ip,
            prefixlen=lease.subnet_mask,
            broadcast=lease.broadcast_address,
        )


@hook(Trigger.BOUND)
async def add_default_gw(lease: Lease):
    '''Configures the default gateway set in the lease.

    Use in addition to `remove_default_gw` for cleanup.
    '''
    LOG.info(
        'Adding %s as default route through %s',
        lease.default_gateway,
        lease.interface,
    )
    async with AsyncIPRoute() as ipr:
        ifindex = (await ipr.link_lookup(ifname=lease.interface),)
        await ipr.route(
            'replace',
            dst='0.0.0.0/0',
            gateway=lease.default_gateway,
            oif=ifindex,
        )


@hook(Trigger.UNBOUND, Trigger.EXPIRED)
async def remove_default_gw(lease: Lease):
    '''Removes the default gateway set in the lease.'''
    LOG.info('Removing %s as default route', lease.default_gateway)
    async with AsyncIPRoute() as ipr:
        ifindex = await ipr.link_lookup(ifname=lease.interface)
        try:
            await ipr.route(
                'del',
                dst='0.0.0.0/0',
                gateway=lease.default_gateway,
                oif=ifindex,
            )
        except NetlinkError as err:
            if err.code == errno.ESRCH:
                LOG.warning(
                    'Default route was already removed by another process'
                )
            LOG.error('Got a netlink error: %s', err)
