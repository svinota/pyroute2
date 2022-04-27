import os
import uuid
import errno
import pytest
import getpass
import logging
import functools
from socket import AF_INET
from socket import AF_INET6
from collections import namedtuple
from utils import allocate_network
from utils import free_network
from pr2modules import netns
from pr2modules.ndb.main import NDB
from pr2modules.nslink.nslink import NetNS
from pr2modules.iproute.linux import IPRoute
from pr2modules.netlink.generic.wireguard import WireGuard
from pr2modules.netlink.exceptions import NetlinkError
from pr2modules.common import uifname
from pr2modules.common import basestring


def skip_if_not_implemented(func):
    @functools.wraps(func)
    def test_wrapper(context):
        try:
            return func(context)
        except (AttributeError, NotImplementedError):
            pytest.skip('feature not implemented')

    return test_wrapper


def skip_if_not_supported(func):
    @functools.wraps(func)
    def test_wrapper(context):
        try:
            return func(context)
        except NetlinkError as e:
            if set((e.code, e.extra_code)) >= {errno.EOPNOTSUPP}:
                pytest.skip('feature not supported by platform')
            raise

    return test_wrapper


def make_test_matrix(targets=None, tables=None, dbs=None, types=None):
    targets = targets or ['local']
    tables = tables or [None]
    types = types or [None]
    dbs = dbs or ['sqlite3/:memory:']
    ret = []
    skipdb = list(filter(lambda x: x, os.environ.get('SKIPDB', '').split(':')))
    for db in dbs:
        db_provider, db_spec = db.split('/')
        if any(map(db_provider.startswith, skipdb)):
            continue
        if db_provider != 'sqlite3':
            db_spec = {'dbname': db_spec}
            user = os.environ.get('PGUSER')
            port = os.environ.get('PGPORT')
            host = os.environ.get('PGHOST')
            if user:
                db_spec['user'] = user
            if host:
                if not port:
                    db_spec['port'] = 5432
                db_spec['host'] = host
            if port:
                if not host:
                    db_spec['host'] = 'localhost'
                db_spec['port'] = port

        for target in targets:
            for table in tables:
                for kind in types:
                    param_id = f'db={db} ' f'target={target}'
                    if table is not None:
                        param_id += f' table={table}'
                    if kind is not None:
                        param_id += f' kind={kind}'
                    param = pytest.param(
                        ContextParams(
                            db_provider, db_spec, target, table, kind
                        ),
                        id=param_id,
                    )
                    ret.append(param)
    return ret


ContextParams = namedtuple(
    'ContextParams', ('db_provider', 'db_spec', 'target', 'table', 'kind')
)

Interface = namedtuple('Interface', ('index', 'ifname'))
Network = namedtuple('Network', ('family', 'network', 'netmask'))


class SpecContextManager(object):
    '''
    Prepare simple common variables
    '''

    def __init__(self, request, tmpdir):
        self.uid = str(uuid.uuid4())
        self.log_spec = (
            '%s/ndb-%s-%s.log' % (tmpdir, os.getpid(), self.uid),
            logging.DEBUG,
        )
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

        target = 'local'
        self.table = None
        self.kind = None
        kwarg['db_provider'] = 'sqlite3'
        kwarg['db_spec'] = ':memory:'
        if hasattr(request, 'param'):
            if isinstance(request.param, ContextParams):
                target = request.param.target
                self.table = request.param.table
                self.kind = request.param.kind
                kwarg['db_provider'] = request.param.db_provider
                kwarg['db_spec'] = request.param.db_spec
            elif isinstance(request.param, (tuple, list)):
                target, self.table = request.param
            else:
                target = request.param

        if target == 'local':
            sources = [{'target': 'localhost', 'kind': 'local'}]
        elif target == 'netns':
            self.netns = self.new_nsname
            sources = [
                {'target': 'localhost', 'kind': 'netns', 'netns': self.netns}
            ]
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
        self.ipr = self.ndb.sources['localhost'].nl.clone()
        self.wg = WireGuard()
        #
        # IPAM
        self.ipnets = [allocate_network() for _ in range(5)]
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        self.allocated_networks = {AF_INET: [], AF_INET6: []}
        #
        # RPDB objects for cleanup
        self.rules = []
        #
        # default interface (if running as root)
        if getpass.getuser() == 'root':
            ifname = self.new_ifname
            index = self.ndb.interfaces.create(
                ifname=ifname, kind='dummy', state='up'
            ).commit()['index']
            self.default_interface = Interface(index, ifname)
        else:
            self.default_interface = None

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

    def register_rule(self, spec, netns=None):
        '''
        Register IP rule for cleanup on `teardown()`.
        '''
        self.rules.append((netns, spec))
        return spec

    def register_network(self, family=AF_INET, network=None):
        '''
        Register or allocate a network.

        All the allocated networks should be deallocated on `teardown()`.
        '''
        if network is None:
            network = allocate_network(family)
        # regsiter for cleanup
        self.allocated_networks[family].append(network)
        # return a simple convenient named tuple
        return Network(family, network.network.format(), network.prefixlen)

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
    def new_ip6net(self):
        '''
        Returns a new IPv6 network
        '''
        return self.register_network(family=AF_INET6)

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
        self.ipr.close()
        self.wg.close()
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
        for nsname, rule in self.rules:
            try:
                ipr = None
                if nsname is not None:
                    ipr = NetNS(nsname)
                else:
                    ipr = IPRoute()
                ipr.rule('del', **rule)
            except NetlinkError as e:
                if e.code != errno.ENOENT:
                    raise
            finally:
                if ipr is not None:
                    ipr.close()
        for net in self.ipnets:
            free_network(net)
        for family, networks in self.allocated_networks.items():
            for net in networks:
                free_network(net, family)
