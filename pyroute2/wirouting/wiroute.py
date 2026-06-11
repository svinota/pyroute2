""" High-level API built on top of AsyncIPRoute.

This module provides:
    * Python dataclasses for parsed objects from kernel.
      You don't need to know NLA attributes names to use it.
    * Specialized exceptions, so caller does not have to check error code
      for most commons errors.
    * Default netlink flags strict_check and ext_ack enabled
    * Python typing
"""

from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.wirouting.exception import exception_factory
from pyroute2.wirouting.link import WiRouteLink
from pyroute2.wirouting.route import WiRouteRoute


class WiRoute(WiRouteLink, WiRouteRoute, AsyncIPRoute):

    def __init__(self, *args, **kwargs):
        for key in ("ext_ack", "strict_check"):
            kwargs.setdefault(key, True)
            kwargs[key] = bool(kwargs[key])
        kwargs.setdefault("exception_factory", exception_factory)
        super().__init__(*args, **kwargs)
