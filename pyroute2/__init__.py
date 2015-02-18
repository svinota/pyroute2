##
# defer all root imports
#
# this allows to safely import config, change it, and
# only after that import modules itself
#
# surely, you can also import modules directly from their
# places
##
from functools import partial

__all__ = []
_modules = {'IPRoute': 'pyroute2.iproute',
            'IPDB': 'pyroute2.ipdb',
            'IW': 'pyroute2.iwutil',
            'NetNS': 'pyroute2.netns',
            'IPRSocket': 'pyroute2.netlink.rtnl',
            'TaskStats': 'pyroute2.netlink.taskstats',
            'NL80211': 'pyroute2.netlink.nl80211',
            'IPQSocket': 'pyroute2.netlink.ipq',
            'GenericNetlinkSocket': 'pyroute2.netlink.generic',
            'NetlinkError': 'pyroute2.netlink'}


def _wrapper(name, *argv, **kwarg):
    _temp = __import__(_modules[name], globals(), locals(), [name], 0)
    return getattr(_temp, name)(*argv, **kwarg)

for name in _modules:
    f = partial(_wrapper, name)
    f.__name__ = name
    globals()[name] = f
    __all__.append(name)
