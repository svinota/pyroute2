'''Lease classes used by the dhcp client.'''

import abc
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from logging import getLogger
from pathlib import Path

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
    # Timestamp of when this lease was obtained
    obtained: float = field(default_factory=_now)

    def _seconds_til_timer(self, timer_name: str) -> float | None:
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
    def expiration_in(self) -> float | None:
        return self._seconds_til_timer('lease')

    @property
    def renewal_in(self) -> float | None:
        '''The amount of seconds before we have to renew the lease.

        Can be negative if it's past due,
        or `None` if the server didn't give a renewal time.
        '''
        return self._seconds_til_timer('renewal')

    @property
    def rebinding_in(self) -> float | None:
        '''The amount of seconds before we have to rebind the lease.

        Can be negative if it's past due,
        or `None` if the server didn't give a rebinding time.
        '''
        return self._seconds_til_timer('rebinding')

    @property
    def ip(self) -> str:
        '''The IP address assigned to the client.'''
        return self.ack['yiaddr']

    @property
    def subnet_mask(self) -> str:
        '''The subnet mask assigned to the client.'''
        return self.ack['options']['subnet_mask']

    @property
    def routers(self) -> str:
        return self.ack['options']['router']

    @property
    def name_servers(self) -> str:  # XXX: list ?
        return self.ack['options']['name_server']

    @property
    def server_id(self) -> str:
        '''The IP address of the server which allocated this lease.'''
        return self.ack['options']['server_id']

    @abc.abstractmethod
    def dump(self) -> None:
        '''Write a lease, i.e. to disk or to stdout.'''
        pass

    @classmethod
    @abc.abstractmethod
    def load(cls, interface: str) -> 'Lease | None':
        '''Load an existing lease for an interface, if it exists.'''
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
    def load(cls, interface: str) -> 'JSONFileLease | None':
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
