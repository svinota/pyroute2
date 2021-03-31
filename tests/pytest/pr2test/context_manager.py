import os
import uuid
import errno
import pytest
import logging
from collections import namedtuple
from utils import allocate_network
from utils import free_network
from pyroute2 import netns
from pyroute2 import NDB
from pyroute2 import NetNS
from pyroute2 import IPRoute
from pyroute2 import NetlinkError
from pyroute2.common import uifname
from pyroute2.common import basestring


def make_test_matrix(targets=None, tables=None, dbs=None):
    targets = targets or ['local', ]
    tables = tables or [None, ]
    dbs = dbs or ['sqlite3/:memory:', ]
    ret = []
    for db in dbs:
        db_provider, db_spec = db.split('/')
        if db_provider != 'sqlite3':
            db_spec = {'dbname': db_spec}
        for target in targets:
            for table in tables:
                param_id = 'db=%s target=%s table=%s' % (db, target, table)
                param = pytest.param(
                    ContextParams(db_provider, db_spec, target, table),
                    id=param_id
                )
                ret.append(param)
    return ret


ContextParams = namedtuple('ContextParams',
                           ('db_provider', 'db_spec', 'target', 'table'))


class SpecContextManager(object):
    '''
    Prepare simple common variables
    '''

    def __init__(self, request, tmpdir):
        self.uid = str(uuid.uuid4())
        self.log_spec = ('%s/ndb-%s-%s.log' % (tmpdir, os.getpid(), self.uid),
                         logging.DEBUG)
        self.db_spec = '%s/ndb-%s-%s.sql' % (tmpdir, os.getpid(), self.uid)

    def teardown(self):
        pass


class NDBContextManager(object):
    '''
    This class is used to manage fixture contexts.

    * create log spec
    * create NDB with specified parameters
    * provide methods to register interfaces
    * automatically remove registered interfaces
    '''

    def __init__(self, request, tmpdir, **kwarg):

        self.spec = SpecContextManager(request, tmpdir)
        self.netns = None
        #
        # the cleanup registry
        self.interfaces = {}
        self.namespaces = {}

        if 'log' not in kwarg:
            kwarg['log'] = self.spec.log_spec
        if 'rtnl_debug' not in kwarg:
            kwarg['rtnl_debug'] = True

        kind = 'local'
        self.table = None
        kwarg['db_provider'] = 'sqlite3'
        kwarg['db_spec'] = ':memory:'
        if hasattr(request, 'param'):
            if isinstance(request.param, ContextParams):
                kind = request.param.target
                self.table = request.param.table
                kwarg['db_provider'] = request.param.db_provider
                kwarg['db_spec'] = request.param.db_spec
            elif isinstance(request.param, (tuple, list)):
                kind, self.table = request.param
            else:
                kind = request.param

        if kind == 'local':
            sources = [{'target': 'localhost', 'kind': 'local'}]
        elif kind == 'netns':
            self.netns = self.new_nsname
            sources = [{'target': 'localhost',
                        'kind': 'netns',
                        'netns': self.netns}]
        else:
            sources = None

        if sources is not None:
            kwarg['sources'] = sources
        #
        # select the DB to work on
        db_name = os.environ.get('PYROUTE2_TEST_DBNAME')
        if isinstance(db_name, basestring) and len(db_name):
            kwarg['db_provider'] = 'psycopg2'
            kwarg['db_spec'] = {'dbname': db_name}
        #
        # this instance is to be tested, so do NOT use it
        # in utility methods
        self.ndb = NDB(**kwarg)
        self.ipr = self.ndb.sources['localhost'].nl
        #
        # IPAM
        self.ipnets = [allocate_network() for _ in range(5)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]

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

    def get_ipaddr(self, r=0):
        '''
        Returns an ip address from the specified range.
        '''
        return str(self.ipranges[r].pop())

    @property
    def new_ifname(self):
        '''
        Returns a new unique ifname and registers it to be
        cleaned up on `self.teardown()`
        '''
        return self.register()

    @property
    def new_ipaddr(self):
        '''
        Returns a new ipaddr from the configured range
        '''
        return self.get_ipaddr()

    @property
    def new_nsname(self):
        '''
        Returns a new unique nsname and registers it to be
        removed on `self.teardown()`
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
        for net in self.ipnets:
            free_network(net)
