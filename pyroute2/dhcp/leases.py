'''Lease classes used by the dhcp client.'''

import abc
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import Optional

from pyroute2.common import dqn2int
from pyroute2.dhcp.dhcp4msg import dhcp4msg

LOG = getLogger(__name__)


def _now() -> float:
    '''The current timestamp.'''
    return datetime.now().timestamp()


@dataclass
class Lease(abc.ABC):
    '''Represents a lease obtained through DHCP.'''

    # The DHCP ack sent by the server which allocated this lease
    ack: dhcp4msg
    # Name of the interface for which this lease was requested
    interface: str
    # MAC address of the server that allocated the lease
    server_mac: str
    # Timestamp of when this lease was obtained
    obtained: float = field(default_factory=_now)

    def _seconds_til_timer(self, timer_name: str) -> Optional[float]:
        '''The number of seconds to wait until the given timer expires.

        The value is fetched from options as `{timer_name}_time`.
        (lease -> lease_time, renewal -> renewal_time, ...)
        '''
        try:
            delta: int = self.ack['options'][f'{timer_name}_time']
            return self.obtained + delta - _now()
        except KeyError:
            return None

    @property
    def expired(self) -> bool:
        '''Whether this lease has expired (its expiration is in the past).

        When loading a persisted lease, this won't be correct if the clock
        has been adjusted since the lease was written.
        However the worst case scenario is that we send a REQUEST for it,
        get a NAK and restart from scratch.
        '''
        return self.expiration_in is not None and self.expiration_in <= 0

    @property
    def expiration_in(self) -> Optional[float]:
        '''The amount of seconds before the lease expires.

        Computed from the `lease_time` option.

        Can be negative if it's past due,
        or `None` if the server didn't give an expiration time.
        '''
        return self._seconds_til_timer('lease')

    @property
    def renewal_in(self) -> Optional[float]:
        '''The amount of seconds before we have to renew the lease.

        Computed from the `renewal_time` option.

        Can be negative if it's past due,
        or `None` if the server didn't give a renewal time.
        '''
        return self._seconds_til_timer('renewal')

    @property
    def rebinding_in(self) -> Optional[float]:
        '''The amount of seconds before we have to rebind the lease.

        Computed from the `rebinding_time` option.

        Can be negative if it's past due,
        or `None` if the server didn't give a rebinding time.
        '''
        return self._seconds_til_timer('rebinding')

    @property
    def ip(self) -> str:
        '''The IP address assigned to the client.'''
        return self.ack['yiaddr']

    @property
    def subnet_mask(self) -> Optional[int]:
        '''The subnet mask assigned to the client.'''
        mask = self.ack['options'].get('subnet_mask')
        if mask is None:
            return None
        if isinstance(mask, int) or mask.isdigit():
            return int(mask)
        return dqn2int(mask)

    @property
    def routers(self) -> list[str]:
        return self.ack['options'].get('router', [])

    @property
    def name_servers(self) -> str:  # XXX: list ?
        return self.ack['options']['name_server']

    @property
    def default_gateway(self) -> Optional[str]:
        '''The default gateway for this interface.

        As mentioned by the RFC, the first router is the most prioritary.
        '''
        return self.routers[0] if self.routers else None

    @property
    def broadcast_address(self) -> Optional[str]:
        '''The broadcast address for this network.'''
        return self.ack['options'].get('broadcast_address')

    @property
    def mtu(self) -> Optional[int]:
        '''The MTU for this interface.'''
        return self.ack['options'].get('interface_mtu')

    @property
    def name_servers(self) -> Optional[str]:  # XXX: list ?
        return self.ack['options'].get('name_server')

    @property
    def server_id(self) -> Optional[str]:
        '''The IP address of the server which allocated this lease.'''
        return self.ack['options'].get('server_id')

    @abc.abstractmethod
    def dump(self) -> None:
        '''Write a lease, i.e. to disk or to stdout.'''
        pass

    @classmethod
    @abc.abstractmethod
    def load(cls, interface: str) -> 'Optional[Lease]':
        '''Load an existing lease for an interface, if it exists.

        The lease is not checked for freshness, and will be None if no lease
        could be loaded.
        '''
        pass


class JSONStdoutLease(Lease):
    '''Just prints the lease to stdout when the client gets a new one.'''

    def dump(self) -> None:
        """Writes the lease as json to stdout."""
        print(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, interface: str) -> None:
        '''Does not do anything.'''
        return None


class JSONFileLease(Lease):
    '''Write and load the lease from a JSON file in the working directory.'''

    @classmethod
    def _get_lease_dir(cls) -> Path:
        '''Where to store the lease file, i.e. the working directory.'''
        return Path.cwd()

    @classmethod
    def _get_path(cls, interface: str) -> Path:
        '''The lease file, named after the interface.'''
        return (
            cls._get_lease_dir().joinpath(interface).with_suffix('.lease.json')
        )

    def dump(self) -> None:
        '''Dump the lease to a file.

        The lease file is named after the interface
        and written in the working directory.
        '''
        lease_path = self._get_path(self.interface)
        LOG.info('Writing lease for %s to %s', self.interface, lease_path)
        with lease_path.open('wt') as lf:
            json.dump(asdict(self), lf, indent=2)

    @classmethod
    def load(cls, interface: str) -> 'Optional[JSONFileLease]':
        '''Load the lease from a file.

        The lease file is named after the interface
        and read from the working directory.
        '''
        lease_path = cls._get_path(interface)
        try:
            with lease_path.open('rt') as lf:
                LOG.info('Loading lease for %s from %s', interface, lease_path)
                return cls(**json.load(lf))
        except FileNotFoundError:
            LOG.info('No existing lease at %s for %s', lease_path, interface)
            return None
        except TypeError as err:
            LOG.warning("Error loading lease: %s", err)
            return None
