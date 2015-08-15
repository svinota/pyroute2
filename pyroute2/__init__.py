##
# Defer all root imports
#
# This allows to safely import config, change it, and
# only after that actually run imports, though the
# import statement can be on the top of the file
#
# Viva PEP8, morituri te salutant!
#
# Surely, you still can import modules directly from their
# places, like `from pyroute2.iproute import IPRoute`
##
from abc import ABCMeta

__all__ = []
_modules = {'IPRoute': 'pyroute2.iproute',
            'RawIPRoute': 'pyroute2.iproute',
            'IPSet': 'pyroute2.ipset',
            'IPDB': 'pyroute2.ipdb',
            'IW': 'pyroute2.iwutil',
            'NetNS': 'pyroute2.netns.nslink',
            'NSPopen': 'pyroute2.netns.process.proxy',
            'IPRSocket': 'pyroute2.netlink.rtnl.iprsocket',
            'IPRouteRequest': 'pyroute2.netlink.rtnl.req',
            'IPLinkRequest': 'pyroute2.netlink.rtnl.req',
            'TaskStats': 'pyroute2.netlink.taskstats',
            'NL80211': 'pyroute2.netlink.nl80211',
            'IPQSocket': 'pyroute2.netlink.ipq',
            'GenericNetlinkSocket': 'pyroute2.netlink.generic',
            'NetlinkError': 'pyroute2.netlink'}

_DISCLAIMER = '''\n\nNotice:\n
This is a proxy class. To read full docs, please run
the `help()` method on the instance instead.

Usage of the proxy allows to postpone the module load,
thus providing a safe way to substitute base classes,
if it is required. More details see in the `pyroute2.config`
module.
\n'''


def _bake(name):

    class Doc(str):

        def __init__(self, registry, *argv, **kwarg):
            self.registry = registry
            super(Doc, self).__init__(*argv, **kwarg)

        def __repr__(self):
            return repr(self.registry['doc'])

        def __str__(self):
            return str(self.registry['doc'])

        def expandtabs(self, ts=4):
            return self.registry['doc'].expandtabs(ts)

    class Registry(object):
        def __init__(self):
            self.target = {}

        def __getitem__(self, key):
            if not self.target:
                module = __import__(_modules[name],
                                    globals(),
                                    locals(),
                                    [name], 0)
                self.target['class'] = getattr(module, name)
                self.target['doc'] = self.target['class'].__doc__
                try:
                    self.target['doc'] += _DISCLAIMER
                except TypeError:
                    # ignore cases, when __doc__ is not a string, e.g. None
                    pass
            return self.target[key]

    @classmethod
    def __hook__(cls, C):
        if hasattr(C, 'registry'):
            try:
                return issubclass(C.registry['class'], cls.registry['class'])
            except Exception:
                pass
        return issubclass(C, cls.registry['class'])

    def __new__(cls, *argv, **kwarg):
        cls.register(cls.registry['class'])
        return cls.registry['class'](*argv, **kwarg)

    registry = Registry()
    doc = Doc(registry)

    proxy = ABCMeta('proxy', (object, ), {'__new__': __new__,
                                          '__doc__': doc,
                                          '__subclasshook__': __hook__,
                                          'registry': registry})
    return proxy


for name in _modules:
    f = _bake(name)
    globals()[name] = f
    __all__.append(name)
