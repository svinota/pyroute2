import asyncio
from argparse import ArgumentParser
from dataclasses import dataclass
from ipaddress import IPv4Address
from shutil import which
from typing import AsyncGenerator, ClassVar, Literal

import pytest
import pytest_asyncio
from fixtures.interfaces import DHCPRangeConfig


@dataclass
class DnsmasqOptions:
    '''Options for the dnsmasq server.'''

    range_start: IPv4Address
    range_end: IPv4Address
    interface: str
    lease_time: str = '12h'

    def __iter__(self):
        opts = (
            f'--interface={self.interface}',
            f'--dhcp-range={self.range_start},'
            f'{self.range_end},{self.lease_time}',
        )
        return iter(opts)


class DnsmasqFixture:
    '''Runs the dnsmasq server as an async context manager.'''

    DNSMASQ_PATH: ClassVar[str | None] = which('dnsmasq')

    def __init__(self, options: DnsmasqOptions) -> None:
        self.options = options
        self.stdout: list[bytes] = []
        self.stderr: list[bytes] = []
        self.process: asyncio.subprocess.Process | None = None
        self.output_poller: asyncio.Task | None = None

    async def _read_output(self, name: Literal['stdout', 'stderr']):
        '''Read stdout or stderr until the process exits.'''
        stream = getattr(self.process, name)
        output = getattr(self, name)
        while line := await stream.readline():
            output.append(line)

    async def _read_outputs(self):
        '''Read stdout & stderr until the process exits.'''
        assert self.process
        await asyncio.gather(
            self._read_output('stderr'), self._read_output('stdout')
        )

    def _get_base_cmdline_options(self) -> tuple[str]:
        '''The base commandline options for dnsmasq.'''
        return (
            '--keep-in-foreground',  # self explanatory
            '--no-resolv',  # don't mess w/ resolv.conf
            '--log-facility=-',  # log to stdout
            '--no-hosts',  # don't read /etc/hosts
            '--bind-interfaces',  # don't bind on wildcard
            '--no-ping',  # don't ping to check if ips are attributed
        )

    def get_cmdline_options(self) -> tuple[str]:
        '''All commandline options passed to dnsmasq.'''
        return (*self._get_base_cmdline_options(), *self.options)

    async def __aenter__(self):
        '''Start the dnsmasq process and start polling its output.'''
        assert self.DNSMASQ_PATH
        self.process = await asyncio.create_subprocess_exec(
            self.DNSMASQ_PATH,
            *self.get_cmdline_options(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={'LANG': 'C'},
        )
        self.output_poller = asyncio.Task(self._read_outputs())
        return self

    async def __aexit__(self, *_):
        if self.process:
            if self.process.returncode is None:
                self.process.terminate()
            await self.process.wait()
            await self.output_poller


@pytest.fixture
def dnsmasq_options(
    veth_pair: tuple[str, str], dhcp_range: DHCPRangeConfig
) -> DnsmasqOptions:
    '''dnsmasq options useful for test purposes.'''
    return DnsmasqOptions(
        range_start=dhcp_range.range_start,
        range_end=dhcp_range.range_end,
        interface=veth_pair[0],
    )


@pytest_asyncio.fixture
async def dnsmasq(
    dnsmasq_options: DnsmasqOptions,
) -> AsyncGenerator[DnsmasqFixture, None]:
    '''A dnsmasq instance running for the duration of the test.'''
    async with DnsmasqFixture(options=dnsmasq_options) as dnsf:
        yield dnsf


def get_psr() -> ArgumentParser:
    psr = ArgumentParser()
    psr.add_argument('interface', help='Interface to listen on')
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
        default='2m',
        help='DHCP lease time (minimum 2 minutes according to man)',
    )
    return psr


async def main():
    '''Commandline entrypoint to start dnsmasq the same way the fixture does.

    Useful for debugging.
    '''
    args = get_psr().parse_args()
    opts = DnsmasqOptions(**args.__dict__)
    read_lines: int = 0
    async with DnsmasqFixture(opts) as dnsm:
        # quick & dirty stderr polling
        while True:
            if len(dnsm.stderr) > read_lines:
                read_lines += len(lines := dnsm.stderr[read_lines:])
                print(*(i.decode().strip() for i in lines), sep='\n')
            else:
                await asyncio.sleep(0.2)


if __name__ == '__main__':
    asyncio.run(main())
