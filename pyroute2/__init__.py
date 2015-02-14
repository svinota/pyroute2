import os
if os.environ.get('PYROUTE2_NO_AUTOIMPORT') is None:
    from pyroute2.iproute import IPRoute
    from pyroute2.ipdb import IPDB
    from pyroute2.netns import NetNS
    from pyroute2.netlink.rtnl import IPRSocket
    from pyroute2.netlink.taskstats import TaskStats
    from pyroute2.netlink.nl80211 import NL80211
    from pyroute2.netlink.ipq import IPQSocket
    from pyroute2.netlink.generic import GenericNetlinkSocket
    from pyroute2.netlink import NetlinkError

    modules = [IPRSocket,
               IPRoute,
               IPDB,
               NetNS,
               TaskStats,
               IPQSocket,
               GenericNetlinkSocket,
               NetlinkError,
               NL80211]

    __all__ = [getattr(module, '__name__') for module in modules]
