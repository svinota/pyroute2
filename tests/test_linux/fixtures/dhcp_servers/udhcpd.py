import asyncio
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from typing import AsyncGenerator, ClassVar, Optional

import pytest
import pytest_asyncio

from ..interfaces import DHCPRangeConfig
from . import DHCPServerConfig, DHCPServerFixture, run_fixture_as_main


@dataclass
class UdhcpdConfig(DHCPServerConfig):
    arp_ping_timeout_ms: int = 200  # default is 2000


class UdhcpdFixture(DHCPServerFixture[UdhcpdConfig]):
    '''Runs the udhcpd server as an async context manager.'''

    BINARY_PATH: ClassVar[Optional[str]] = which('busybox')

    def __init__(self, config):
        super().__init__(config)
        self._temp_dir: Optional[TemporaryDirectory[str]] = None

    @property
    def workdir(self) -> Path:
        '''A temporary directory for udhcpd's files.'''
        assert self._temp_dir
        return Path(self._temp_dir.name)

    @property
    def config_file(self) -> Path:
        '''The udhcpd config file path.'''
        return self.workdir.joinpath("udhcpd.conf")

    async def __aenter__(self):
        self._temp_dir = TemporaryDirectory(prefix=type(self).__name__)
        self._temp_dir.__enter__()
        self.config_file.write_text(self.generate_config())
        return await super().__aenter__()

    def generate_config(self) -> str:
        '''Generate the contents of udhcpd's config file.'''
        cfg = self.config
        base_workfile = self.workdir.joinpath(self.config.interface)
        lease_file = base_workfile.with_suffix(".leases")
        pidfile = base_workfile.with_suffix(".pid")
        lines = [
            ("start", cfg.range.start),
            ("end", cfg.range.end),
            ("max_leases", cfg.max_leases),
            ("interface", cfg.interface),
            ("lease_file", lease_file),
            ("pidfile", pidfile),
            ("opt lease", cfg.lease_time),
            ("opt subnet", cfg.range.netmask),
        ]
        if router := cfg.range.router:
            lines.append(("opt router", router))
        return "\n".join(f"{opt}\t{value}" for opt, value in lines)

    async def __aexit__(self, *_):
        await super().__aexit__(*_)
        self._temp_dir.__exit__(*_)

    def get_cmdline_options(self) -> tuple[str]:
        '''All commandline options passed to udhcpd.'''
        return (
            'udhcpd',
            '-f',  # run in foreground
            '-a',
            str(self.config.arp_ping_timeout_ms),
            str(self.config_file),
        )


@pytest.fixture
def udhcpd_config(
    veth_pair: tuple[str, str], dhcp_range: DHCPRangeConfig, lease_time: int
) -> UdhcpdConfig:
    '''udhcpd options useful for test purposes.'''
    return UdhcpdConfig(
        range=dhcp_range, interface=veth_pair[0], lease_time=lease_time
    )


@pytest_asyncio.fixture
async def udhcpd(
    udhcpd_config: UdhcpdConfig,
) -> AsyncGenerator[UdhcpdFixture, None]:
    '''An udhcpd instance running for the duration of the test.'''
    async with UdhcpdFixture(config=udhcpd_config) as dhcp_server:
        yield dhcp_server


if __name__ == '__main__':
    asyncio.run(run_fixture_as_main(UdhcpdFixture))
