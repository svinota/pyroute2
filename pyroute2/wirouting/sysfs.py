"""
Helpers for sysfs
"""

import errno
from functools import cached_property
from pathlib import Path

from pyroute2.wirouting.exception import NotPhyDevice


class InterfaceSysfs:
    """Class Used to introspect interface with sysfs"""

    def __init__(self, name=None):
        if name:
            self.name = name

    name = NotImplemented

    @cached_property
    def sysfs(self) -> Path:
        return Path("/sys/class/net", self.name)

    def is_virtual(self) -> bool:
        """Return True if is a virtual device"""
        return self.sysfs.resolve() == Path(
            "/sys/devices/virtual/net", self.name
        )

    def has_device(self) -> bool:
        """Return True if is a physical device"""
        return (self.sysfs / "device").is_symlink()

    def get_device_driver(self) -> str:
        """Return the device driver name"""
        if not self.has_device():
            raise NotPhyDevice(errno.ENODEV, "Not a physical interface")
        return (self.sysfs / "device" / "driver").readlink().name

    def is_wireless(self) -> bool:
        """Return True if is a wireless device"""
        return any(
            (
                (self.sysfs / "wireless").exists(),
                (self.sysfs / "phy80211").exists(),
            )
        )
