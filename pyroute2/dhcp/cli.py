import asyncio
import logging
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from importlib import import_module
from typing import Any

from pyroute2.dhcp.client import AsyncDHCPClient, ClientConfig
from pyroute2.dhcp.fsm import State
from pyroute2.dhcp.hooks import Hook
from pyroute2.dhcp.iface_status import InterfaceStateWatcher
from pyroute2.dhcp.leases import Lease


def import_dotted_name(name: str) -> Any:
    '''Imports anything by name.'''
    module_name, obj_name = name.rsplit('.', 1)
    module = import_module(module_name)
    return getattr(module, obj_name)


def get_psr() -> ArgumentParser:
    psr = ArgumentParser(
        description='pyroute2 DHCP client',
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    psr.add_argument(
        'interface', help='The interface to request an address for.'
    )
    psr.add_argument(
        '--lease-type',
        help='Class to use for leases. '
        'Must be a subclass of `pyroute2.dhcp.leases.Lease`.',
        type=str,
        default='pyroute2.dhcp.leases.JSONFileLease',
        metavar='dotted.name',
    )
    psr.add_argument(
        '--hook',
        help='Hooks to load. '
        'These are used to run async python code when, '
        'for example, renewing or expiring a lease.',
        nargs='+',
        type=str,
        default=[
            'pyroute2.dhcp.hooks.configure_ip',
            'pyroute2.dhcp.hooks.add_default_gw',
            'pyroute2.dhcp.hooks.remove_default_gw',
            'pyroute2.dhcp.hooks.remove_ip',
        ],
        metavar='dotted.name',
    )
    psr.add_argument(
        '-x',
        '--exit-on-timeout',
        metavar='N',
        help='Wait for max N seconds for a lease, '
        'exit if none could be obtained.',
        type=int,
        default=0,
    )
    psr.add_argument(
        '--log-level',
        help='Logging level to use.',
        choices=('DEBUG', 'INFO', 'WARNING', 'ERROR'),
        default='INFO',
    )
    psr.add_argument(
        '-p',
        '--write-pidfile',
        default=False,
        action='store_true',
        help='Write a pid file in the working directory. '
        'WARNING: this option might be removed later.',
    )
    psr.add_argument(
        '-R',
        '--no-release',
        default=False,
        action='store_true',
        help='Do not send a DHCPRELEASE on exit.',
    )
    # TODO: add options for parameters, retransmission, timeouts...
    return psr


async def main() -> None:
    psr = get_psr()
    args = psr.parse_args()
    logging.basicConfig(
        format='%(asctime)s %(levelname)s [%(name)s:%(funcName)s] %(message)s'
    )
    logging.getLogger('pyroute2.dhcp').setLevel(args.log_level)
    LOG = logging.getLogger(__name__)
    LOG.setLevel(args.log_level)

    # parse lease type
    lease_type = import_dotted_name(args.lease_type)
    if not issubclass(lease_type, Lease):
        psr.error(f'{args.lease_type!r} must point to a Lease subclass.')

    # parse hooks
    hooks: list[Hook] = []
    for dotted_hook_name in args.hook:
        hook = import_dotted_name(dotted_hook_name)
        if not isinstance(hook, Hook):
            psr.error(f'{dotted_hook_name!r} must point to a Hook instance.')
        hooks.append(hook)

    # Create configuration
    cfg = ClientConfig(
        interface=args.interface,
        lease_type=lease_type,
        hooks=hooks,
        write_pidfile=args.write_pidfile,
        release=not args.no_release,
    )

    acli = AsyncDHCPClient(cfg)

    async with InterfaceStateWatcher(cfg.interface) as iface_watcher:
        while True:
            # Open the socket, read existing lease, etc
            if iface_watcher.state != 'up':
                LOG.info("Waiting for %s to go up...", cfg.interface)
            await iface_watcher.up.wait()
            async with acli:
                # Bootstrap the client by sending a DISCOVER or a REQUEST
                await acli.bootstrap()
                if args.exit_on_timeout:
                    # Wait a bit for a lease, and exit if we have none
                    try:
                        await acli.wait_for_state(
                            State.BOUND, timeout=args.exit_on_timeout
                        )
                        break
                    except TimeoutError as err:
                        psr.error(str(err))

                await iface_watcher.down.wait()
                LOG.info("%s went down", cfg.interface)


def run():
    # for the setup.cfg entrypoint
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # raised by "older" python versions on ctrl-C
        pass


if __name__ == '__main__':
    run()
