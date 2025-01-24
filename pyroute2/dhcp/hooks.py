'''Hooks called by the DHCP client when bound, a leases expires, etc.'''

from logging import getLogger

from pyroute2.dhcp.leases import Lease
from pyroute2.iproute.linux import AsyncIPRoute

LOG = getLogger(__name__)


class Hook:
    '''Base class for pyroute2 dhcp client hooks.'''

    def __init__(self, **settings):
        pass

    async def bound(self, lease: Lease):
        '''Called when the client gets a lease.'''
        pass

    async def unbound(self, lease: Lease):
        '''Called when a leases expires.'''
        pass


class ConfigureIP(Hook):
    async def bound(self, lease: Lease):
        LOG.info('Adding %s/%s to %s', lease.ip,
                 lease.subnet_mask, lease.interface)
        async with AsyncIPRoute() as ipr:
            await ipr.addr(
                'replace',
                index=await ipr.link_lookup(ifname=lease.interface),
                address=lease.ip,
                mask=lease.subnet_mask,
                broadcast=lease.broadcast_address
            )

    async def unbound(self, lease: Lease):
        LOG.info('Removing %s/%s from %s', lease.ip,
                 lease.subnet_mask, lease.interface)
        async with AsyncIPRoute() as ipr:
            await ipr.addr(
                'del',
                index=await ipr.link_lookup(ifname=lease.interface),
                address=lease.ip,
                mask=lease.subnet_mask,
                broadcast=lease.broadcast_address
            )
