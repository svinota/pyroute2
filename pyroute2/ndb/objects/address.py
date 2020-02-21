from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg


class Address(RTNL_Object):

    table = 'addresses'
    msg_class = ifaddrmsg
    api = 'addr'
    summary = '''
              SELECT
                  a.f_target, a.f_tflags,
                  i.f_IFLA_IFNAME, a.f_IFA_ADDRESS, a.f_prefixlen
              FROM
                  addresses AS a
              INNER JOIN
                  interfaces AS i
              ON
                  a.f_index = i.f_index
                  AND a.f_target = i.f_target
              '''
    table_alias = 'a'
    summary_header = ('target', 'tflags', 'ifname', 'address', 'prefixlen')
    reverse_update = {'table': 'addresses',
                      'name': 'addresses_f_tflags',
                      'field': 'f_tflags',
                      'sql': '''
                          UPDATE interfaces
                          SET f_tflags = NEW.f_tflags
                          WHERE f_index = NEW.f_index AND
                                f_target = NEW.f_target;
                      '''}

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ifaddrmsg
        self.event_map = {ifaddrmsg: "load_rtnlmsg"}
        super(Address, self).__init__(*argv, **kwarg)

    @classmethod
    def adjust_spec(cls, spec, context):
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
