import asyncio
import logging
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from importlib import import_module
from typing import Any

from pyroute2.dhcp import hooks
from pyroute2.dhcp.client import AsyncDHCPClient, ClientConfig
from pyroute2.dhcp.fsm import State
from pyroute2.dhcp.leases import Lease


def importable(name: str) -> Any:
    '''Imports anything by name. Used by the argument parser.'''
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
        type=importable,
        default='pyroute2.dhcp.leases.JSONFileLease',
        metavar='dotted.name',
    )
    psr.add_argument(
        '--hook',
        help='Hooks to load. '
        'These are used to run async python code when, '
        'for example, renewing or expiring a lease.',
        nargs='+',
        type=importable,
        default=[
            hooks.configure_ip,
            hooks.add_default_gw,
            hooks.remove_default_gw,
            hooks.remove_ip,
        ],
        metavar='dotted.name',
    )
    psr.add_argument(
        '-x',
        '--exit-on-lease',
        help='Exit as soon as getting a lease.',
        default=False,
        action='store_true',
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
        action="store_true",
        help="Write a pid file in the working directory.",
    )
    return psr


async def main():
    psr = get_psr()
    args = psr.parse_args()
    logging.basicConfig(
        format='%(asctime)s %(levelname)s [%(name)s:%(funcName)s] %(message)s'
    )
    logging.getLogger('pyroute2.dhcp').setLevel(args.log_level)
    if not issubclass(args.lease_type, Lease):
        psr.error(f'{args.lease_type!r} must be a Lease subclass')

    cfg = ClientConfig(
        interface=args.interface,
        lease_type=args.lease_type,
        hooks=args.hook,
        write_pidfile=args.write_pidfile,
    )

    # Open the socket, read existing lease, etc
    async with AsyncDHCPClient(cfg) as acli:
        # Bootstrap the client by sending a DISCOVER or a REQUEST
        await acli.bootstrap()
        if args.exit_on_lease:
            # Wait until we're bound once, then exit
            await acli.wait_for_state(State.BOUND)
        else:
            # Wait until the client is stopped otherwise
            await acli.wait_for_state(State.OFF)


def run():
    # for the setup.cfg entrypoint
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    run()
