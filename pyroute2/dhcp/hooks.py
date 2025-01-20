'''Hooks called by the DHCP client when bound, a leases expires, etc.'''

from logging import getLogger

from pyroute2.dhcp.leases import Lease

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
        LOG.info('STUB: add %s to %s', lease.ip, lease.interface)
        # await ip(
        #     "addr",
        #     "replace",
        #     f"{lease.ip}/{lease.subnet_mask}",
        #     "dev",
        #     lease.interface,
        # )

    async def unbound(self, lease: Lease):
        LOG.info('STUB: remove %s from %s', lease.ip, lease.interface)
        # await ip(
        #     "addr",
        #     "del",
        #     f"{lease.ip}/{lease.subnet_mask}",
        #     "dev",
        #     lease.interface,
        # )
