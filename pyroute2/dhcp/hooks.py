'''Hooks called by the DHCP client when bound, a leases expires, etc.'''

import errno
from logging import getLogger

from pyroute2.dhcp.leases import Lease
from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.netlink.exceptions import NetlinkError

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


class ConfigureDefaultRoute(Hook):
    async def bound(self, lease: Lease):
        if lease.default_gateway is None:
            LOG.error('Lease does not set the router option')
            return
        LOG.info('Adding %s as default route through %s',
                 lease.default_gateway, lease.interface)
        async with AsyncIPRoute() as ipr:
            ifindex = await ipr.link_lookup(ifname=lease.interface),
            await ipr.route(
                'replace',
                dst='0.0.0.0/0',
                gateway=lease.default_gateway,
                oif=ifindex
            )

    async def unbound(self, lease: Lease):
        if lease.default_gateway is None:
            LOG.error('Lease does not set the router option')
            return
        LOG.info('Removing %s as default route.', lease.default_gateway)
        async with AsyncIPRoute() as ipr:
            ifindex = await ipr.link_lookup(ifname=lease.interface)
            try:
                await ipr.route(
                    'del',
                    dst='0.0.0.0/0',
                    gateway=lease.default_gateway,
                    oif=ifindex
                )
            except NetlinkError as err:
                if err.code == errno.ESRCH:
                    LOG.warning('Default route was already removed by another process')
                LOG.error('Got a netlink error: %s', err)
