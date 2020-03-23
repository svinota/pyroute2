'''

Using the view
==============

The `addresses` view provides access to all the addresses registered in the DB,
as well as methods to create and remove them::

    eth0 = ndb.interfaces['eth0']

    # create an address
    (ndb
     .addresses
     .create(address='10.0.0.1', prefixlen=24, index=eth0['index'])
     .commit())

    # remove it
    (ndb
     .addresses['10.0.0.1/24']
     .remove()
     .commit())

    # list addresses
    (ndb
     .addresses
     .summary())  # see also other view dump methods

Using interfaces
================

One can use interface objects to inspect addresses as well::

    (ndb
     .interfaces['eth0']
     .ipaddr
     .summary())  # see also other view dump methods

Or to manage them::

    (ndb
     .interfaces['eth0']
     .add_ip('10.0.0.1/24')    # add a new IP address
     .del_ip('172.16.0.1/24')  # remove an existing address
     .set('state', 'up')
     .commit())

Accessing one address details
=============================

Access an address as a separate RTNL object::

    print(ndb.addresses['10.0.0.1/24'])

Please notice that address objects are read-only, you may not change them,
only remove old ones, and create new.
'''
from collections import OrderedDict
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg


init = {'specs': [['addresses', OrderedDict(ifaddrmsg.sql_schema())]],
        'classes': [['addresses', ifaddrmsg]],
        'indices': [['addresses', ('family',
                                   'prefixlen',
                                   'index',
                                   'IFA_ADDRESS',
                                   'IFA_LOCAL')]],
        'foreign_keys': [['addresses', [{'fields': ('f_target',
                                                    'f_tflags',
                                                    'f_index'),
                                         'parent_fields': ('f_target',
                                                           'f_tflags',
                                                           'f_index'),
                                         'parent': 'interfaces'}]]],
        'event_map': {ifaddrmsg: ['addresses']}}


class Address(RTNL_Object):

    table = 'addresses'
    msg_class = ifaddrmsg
    api = 'addr'

    @classmethod
    def _dump_where(cls, view):
        if view.chain:
            plch = view.ndb.schema.plch
            where = '''
                    WHERE
                        main.f_target = %s AND
                        main.f_index = %s
                    ''' % (plch, plch)
            values = [view.chain['target'], view.chain['index']]
        else:
            where = ''
            values = []
        return (where, values)

    @classmethod
    def summary(cls, view):
        req = '''
              SELECT
                  main.f_target, main.f_tflags,
                  intf.f_IFLA_IFNAME, main.f_IFA_ADDRESS, main.f_prefixlen
              FROM
                  addresses AS main
              INNER JOIN
                  interfaces AS intf
              ON
                  main.f_index = intf.f_index
                  AND main.f_target = intf.f_target
              '''
        yield ('target', 'tflags', 'ifname', 'address', 'prefixlen')
        where, values = cls._dump_where(view)
        for record in view.ndb.schema.fetch(req + where, values):
            yield record

    def mark_tflags(self, mark):
        plch = (self.schema.plch, ) * 3
        self.schema.execute('''
                            UPDATE interfaces SET
                                f_tflags = %s
                            WHERE f_index = %s AND f_target = %s
                            ''' % plch, (mark, self['index'], self['target']))

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ifaddrmsg
        self.event_map = {ifaddrmsg: "load_rtnlmsg"}
        super(Address, self).__init__(*argv, **kwarg)

    @classmethod
    def adjust_spec(self, spec, context):
        if context is None:
            context = {}
        if isinstance(spec, basestring):
            ret = {}
            ret['address'], prefixlen = spec.split('/')
            ret['prefixlen'] = int(prefixlen)
            spec = ret
        for key in context:
            if key not in spec:
                spec[key] = context[key]
        return spec

    def key_repr(self):
        return '%s/%s %s/%s' % (self.get('target', ''),
                                self.get('label', self.get('index', '')),
                                self.get('local', self.get('address', '')),
                                self.get('prefixlen', ''))
