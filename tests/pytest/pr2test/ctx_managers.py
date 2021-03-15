import os
import uuid
import errno
import logging
from pyroute2 import netns
from pyroute2 import NDB
from pyroute2 import NetNS
from pyroute2 import IPRoute
from pyroute2 import NetlinkError
from pyroute2.common import uifname


class NDBContextManager(object):
    '''
    This class is used to manage fixture contexts.

    * create log spec
    * create NDB with specified parameters
    * provide methods to register interfaces
    * automatically remove registered interfaces
    '''

    def __init__(self, tmpdir, **kwarg):
        # FIXME: use path provided by pytest, don't hardcode it
        log_id = str(uuid.uuid4())
        log_spec = ('%s/ndb-%s-%s.log' % (tmpdir, os.getpid(), log_id),
                    logging.DEBUG)

        if 'log' not in kwarg:
            kwarg['log'] = log_spec
        if 'rtnl_debug' not in kwarg:
            kwarg['rtnl_debug'] = True
        #
        # this instance is to be tested, so do NOT use it
        # in utility methods
        self.ndb = NDB(**kwarg)
        #
        # the cleanup registry
        self.interfaces = {}
        self.namespaces = {}

    def getspec(self, **kwarg):
        return dict(kwarg)

    def register(self, ifname=None, netns=None):
        '''
        Register an interface in `self.interfaces`. If no interface
        name specified, create a random one.

        All the saved interfaces will be removed on `teardown()`
        '''
        if ifname is None:
            ifname = uifname()
        self.interfaces[ifname] = netns
        return ifname

    def register_netns(self, netns=None):
        '''
        Register netns in `self.namespaces`. If no netns name is
        specified, create a random one.

        All the save namespaces will be removed on `teardown()`
        '''
        if netns is None:
            netns = str(uuid.uuid4())
        self.namespaces[netns] = None
        return netns

    @property
    def ifname(self):
        '''
        Property `self.ifname` returns a new unique ifname and
        registers it to be cleaned up on `self.teardown()`
        '''
        return self.register()

    @property
    def nsname(self):
        '''
        Property `self.nsname` returns a new unique nsname and
        registers it to be removed on `self.teardown()`
        '''
        return self.register_netns()

    def teardown(self):
        '''
        1. close the test NDB
        2. remove the registered interfaces, ignore not existing
        '''
        self.ndb.close()
        for (ifname, nsname) in self.interfaces.items():
            try:
                ipr = None
                #
                # spawn ipr to remove the interface
                if nsname is not None:
                    ipr = NetNS(nsname)
                else:
                    ipr = IPRoute()
                #
                # lookup the interface index
                index = list(ipr.link_lookup(ifname=ifname))
                if len(index):
                    index = index[0]
                else:
                    #
                    # ignore not existing interfaces
                    continue
                #
                # try to remove it
                ipr.link('del', index=index)
            except NetlinkError as e:
                #
                # ignore if removed (t.ex. by another process)
                if e.code != errno.ENODEV:
                    raise
            finally:
                if ipr is not None:
                    ipr.close()
        for nsname in self.namespaces:
            netns.remove(nsname)
