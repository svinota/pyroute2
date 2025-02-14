import abc
import asyncio
from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import ClassVar, DefaultDict, Generic, Literal, Optional, TypeVar

import pytest

from ..interfaces import DHCPRangeConfig


@pytest.fixture
def lease_time() -> int:
    '''Configures the lease time used by dhcp servers.

    Can be overridden in individual tests with
    `@pytest.mark.parametrize('lease_time', [5])`
    '''
    return 120


@dataclass
class DHCPServerConfig:
    range: DHCPRangeConfig
    interface: str
    lease_time: int = 120  # in seconds
    max_leases: int = 50


DHCPServerConfigT = TypeVar("DHCPServerConfigT", bound=DHCPServerConfig)


class DHCPServerFixture(abc.ABC, Generic[DHCPServerConfigT]):

    BINARY_PATH: ClassVar[Optional[str]] = None

    @classmethod
    def get_config_class(cls) -> type[DHCPServerConfigT]:
        return cls.__orig_bases__[0].__args__[0]

    def __init__(self, config: DHCPServerConfigT) -> None:
        self.config = config
        self.stdout: list[str] = []
        self.stderr: list[str] = []
        self.process: Optional[asyncio.subprocess.Process] = None
        self.output_poller: Optional[asyncio.Task] = None
        self.expected_logs: DefaultDict[str, asyncio.Event] = defaultdict(
            asyncio.Event
        )

    async def _read_output(self, name: Literal['stdout', 'stderr']):
        '''Read stdout or stderr until the process exits.'''
        stream: asyncio.StreamReader = getattr(self.process, name)
        output: list[str] = getattr(self, name)
        while line := await stream.readline():
            line = line.decode().strip()
            # Trigger events for any log substring we're looking for
            # that will wake up `wait_for_log`
            for sublog in filter(line.__contains__, self.expected_logs):
                self.expected_logs[sublog].set()
            output.append(line)

    async def _read_outputs(self):
        '''Read stdout & stderr until the process exits.'''
        assert self.process
        await asyncio.gather(
            self._read_output('stderr'), self._read_output('stdout')
        )

    @abc.abstractmethod
    def get_cmdline_options(self) -> tuple[str]:
        '''All commandline options passed to the server.'''

    async def __aenter__(self):
        '''Start the server process and start polling its output.'''
        if not self.BINARY_PATH:
            raise RuntimeError(
                f"server binary is missing for {type(self).__name__}"
            )
        self.process = await asyncio.create_subprocess_exec(
            self.BINARY_PATH,
            *self.get_cmdline_options(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={'LANG': 'C'},  # usually ensures the output is in english
        )
        self.output_poller = asyncio.Task(self._read_outputs())
        return self

    async def __aexit__(self, *_):
        if self.process:
            if self.process.returncode is None:
                self.process.terminate()
            await self.process.wait()
            await self.output_poller

    async def wait_for_log(self, substr: str):
        '''Wait for a string to appear in logs, then return.'''
        await self.expected_logs[substr].wait()
        # wait a tiny bit more so the client has time to react
        await asyncio.sleep(0.1)


def get_psr() -> ArgumentParser:
    psr = ArgumentParser()
    psr.add_argument('interface', help='Interface to listen on')
    psr.add_argument(
        '--router', type=IPv4Address, default=None, help='Router IPv4 address.'
    )
    psr.add_argument(
        '--range-start',
        type=IPv4Address,
        default=IPv4Address('192.168.186.10'),
        help='Start of the DHCP client range.',
    )
    psr.add_argument(
        '--range-end',
        type=IPv4Address,
        default=IPv4Address('192.168.186.100'),
        help='End of the DHCP client range.',
    )
    psr.add_argument(
        '--lease-time',
        default=120,
        type=int,
        help='DHCP lease time  in seconds (minimum 2 minutes)',
    )
    psr.add_argument(
        '--netmask', type=IPv4Address, default=IPv4Address("255.255.255.0")
    )
    psr.add_argument(
        '--broadcast', type=IPv4Address, default=IPv4Address('192.168.186.255')
    )
    return psr


async def run_fixture_as_main(fixture_cls: type[DHCPServerFixture]):
    config_cls = fixture_cls.get_config_class()
    args = get_psr().parse_args()
    range_config = DHCPRangeConfig(
        start=args.range_start,
        end=args.range_end,
        router=args.router,
        netmask=args.netmask,
        broadcast=args.broadcast,
    )
    conf = config_cls(
        range=range_config,
        interface=args.interface,
        lease_time=args.lease_time,
    )
    read_lines: int = 0
    async with fixture_cls(conf) as dhcp_server:
        # quick & dirty stderr polling
        while True:
            if len(dhcp_server.stderr) > read_lines:
                read_lines += len(lines := dhcp_server.stderr[read_lines:])
                print(*lines, sep='\n')
            else:
                await asyncio.sleep(0.2)
