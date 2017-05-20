##
#
# NB: the deferred import code may be removed
#
# That should not affect neither the public API, nor the
# type matching with isinstance() and issubclass()
#
import sys
import struct
import logging
from abc import ABCMeta
from pyroute2.ipdb.exceptions import \
    DeprecationException, \
    CommitException, \
    CreateException, \
    PartialCommitException
from pyroute2.netlink.exceptions import \
    NetlinkError, \
    NetlinkDecodeError

log = logging.getLogger(__name__)
# Add a NullHandler to the library's top-level logger to avoid complaints
# on logging calls when no handler is configured.
# see https://docs.python.org/2/howto/logging.html#library-config
if sys.version_info >= (2, 7):  # This is only available from 2.7 onwards
    log.addHandler(logging.NullHandler())

try:
    # probe, if the bytearray can be used in struct.unpack_from()
    struct.unpack_from('I', bytearray((1, 0, 0, 0)), 0)
except:
    if sys.version_info[0] < 3:
        # monkeypatch for old Python versions
        log.warning('patching struct.unpack_from()')

        def wrapped(fmt, buf, offset=0):
            return struct._u_f_orig(fmt, str(buf), offset)
        struct._u_f_orig = struct.unpack_from
        struct.unpack_from = wrapped
    else:
        raise

# reexport exceptions
exceptions = [NetlinkError,
              NetlinkDecodeError,
              DeprecationException,
              CommitException,
              CreateException,
              PartialCommitException]

__all__ = []
_modules = {'IPRoute': 'pyroute2.iproute',
            'IPBatch': 'pyroute2.iproute',
            'RawIPRoute': 'pyroute2.iproute',
            'IPSet': 'pyroute2.ipset',
            'IPDB': 'pyroute2.ipdb.main',
            'IW': 'pyroute2.iwutil',
            'DL': 'pyroute2.devlink',
            'NetNS': 'pyroute2.netns.nslink',
            'NSPopen': 'pyroute2.netns.process.proxy',
            'IPRSocket': 'pyroute2.netlink.rtnl.iprsocket',
            'IPRouteRequest': 'pyroute2.netlink.rtnl.req',
            'IPLinkRequest': 'pyroute2.netlink.rtnl.req',
            'TaskStats': 'pyroute2.netlink.taskstats',
            'NL80211': 'pyroute2.netlink.nl80211',
            'DevlinkSocket': 'pyroute2.netlink.devlink',
            'AcpiEventSocket': 'pyroute2.netlink.event.acpi_event',
            'DQuotSocket': 'pyroute2.netlink.event.dquot',
            'IPQSocket': 'pyroute2.netlink.ipq',
            'DiagSocket': 'pyroute2.netlink.diag',
            'GenericNetlinkSocket': 'pyroute2.netlink.generic',
            'NFTSocket': 'pyroute2.netlink.nfnetlink.nftables'}


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


class __common(object):
    def __getattribute__(self, key):
        log.warning('module pyroute2.ipdb.common is deprecated, '
                    'use pyroute2.ipdb.exceptions instead')
        return getattr(globals()['ipdb'].exceptions, key)


globals()['ipdb'].common = __common()

__all__.extend([x.__name__ for x in exceptions])
