import collections
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.netlink.rtnl.fibmsg import fibmsg


class Rule(RTNL_Object):

    table = 'rules'
    msg_class = fibmsg
    api = 'rule'
    table_alias = 'n'
    _replace_on_key_change = True
    summary = '''
              SELECT
                f_target, f_tflags, f_family,
                f_FRA_PRIORITY, f_action, f_FRA_TABLE
              FROM
                rules
              '''
    summary_header = ('target', 'tflags', 'family',
                      'priority', 'action', 'table')

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = fibmsg
        self._fields = [x[0] for x in fibmsg.fields]
        self.event_map = {fibmsg: "load_rtnlmsg"}
        super(Rule, self).__init__(*argv, **kwarg)

    def load_sql(self, *argv, **kwarg):
        spec = super(Rule, self).load_sql(*argv, **kwarg)
        if spec is None:
            return
        nkey = collections.OrderedDict()
        for name_norm, name_raw, value in zip(self.names, self.spec, spec):
            if name_raw in self.kspec:
                nkey[name_raw] = value
            if name_norm not in self._fields and value in (0, ''):
                dict.__setitem__(self, name_norm, None)
        self._key = nkey
        return spec
