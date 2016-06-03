import logging
import threading
from collections import namedtuple
from pyroute2.netlink.rtnl.fibmsg import fibmsg
from pyroute2.netlink.rtnl.fibmsg import FR_ACT_NAMES
from pyroute2.ipdb.exceptions import CommitException
from pyroute2.ipdb.transactional import Transactional

log = logging.getLogger(__name__)


RuleKey = namedtuple('RuleKey',
                     ('action',
                      'table',
                      'priority',
                      'iifname',
                      'oifname',
                      'fwmark',
                      'fwmask',
                      'goto',
                      'tun_id'))


class Rule(Transactional):
    '''
    Persistent transactional rule object
    '''

    _fields = [fibmsg.nla2name(i[1]) for i in fibmsg.nla_map]
    for key, _ in fibmsg.fields:
        _fields.append(key)
    _fields.append('removal')
    _virtual_fields = ['ipdb_scope', 'ipdb_priority']
    _fields.extend(_virtual_fields)
    cleanup = ('attrs',
               'header',
               'event',
               'src_len',
               'dst_len',
               'res1',
               'res2')

    @classmethod
    def make_key(cls, msg):
        values = []
        if isinstance(msg, fibmsg):
            for field in RuleKey._fields:
                v = msg.get_attr(msg.name2nla(field))
                if v is None:
                    v = msg.get(field, 0)
                values.append(v)
        elif isinstance(msg, dict):
            for field in RuleKey._fields:
                values.append(msg.get(field, 0))
        else:
            raise TypeError('prime not supported: %s' % type(msg))
        return RuleKey(*values)

    def __init__(self, ipdb, mode=None, parent=None, uid=None):
        Transactional.__init__(self, ipdb, mode, parent, uid)
        with self._direct_state:
            self['ipdb_priority'] = 0

    def load_netlink(self, msg):
        with self._direct_state:
            if self['ipdb_scope'] == 'locked':
                # do not touch locked interfaces
                return

            self['ipdb_scope'] = 'system'
            for (key, value) in msg.items():
                self[key] = value

            # merge NLA
            for cell in msg['attrs']:
                #
                # Parse on demand
                #
                norm = fibmsg.nla2name(cell[0])
                if norm in self.cleanup:
                    continue
                self[norm] = cell[1]

            if msg.get_attr('FRA_DST'):
                dst = '%s/%s' % (msg.get_attr('FRA_DST'),
                                 msg['dst_len'])
                self['dst'] = dst
            if msg.get_attr('FRA_SRC'):
                src = '%s/%s' % (msg.get_attr('FRA_SRC'),
                                 msg['src_len'])
                self['src'] = src

            # finally, cleanup all not needed
            for item in self.cleanup:
                if item in self:
                    del self[item]
        return self

    def commit(self,
               tid=None,
               transaction=None,
               commit_phase=1,
               commit_mask=0xff):

        if not commit_phase & commit_mask:
            return self

        error = None
        drop = True
        devop = 'set'

        if tid:
            transaction = self.global_tx[tid]
        else:
            if transaction:
                drop = False
            else:
                transaction = self.current_tx

        # create a new route
        if self['ipdb_scope'] != 'system':
            devop = 'add'

        # work on an existing route
        snapshot = self.pick()
        added, removed = transaction // snapshot
        added.pop('ipdb_scope', None)
        removed.pop('ipdb_scope', None)

        try:
            # rule add/set
            if any(added.values()) or devop == 'add':

                old_key = self.make_key(self)
                new_key = self.make_key(transaction)

                if new_key != old_key:
                    # check for the key conflict
                    if new_key in self.ipdb.rules:
                        raise CommitException('rule priority conflict')
                    else:
                        self.ipdb.rules[new_key] = self
                        self.nl.rule('del', priority=old_key)
                        self.nl.rule('add', **transaction)
                else:
                    if devop != 'add':
                        with self._direct_state:
                            self['ipdb_scope'] = 'shadow'
                        self.nl.rule('del', priority=old_key)
                        with self._direct_state:
                            self['ipdb_scope'] = 'reload'
                    self.nl.rule('add', **transaction)
                transaction.wait_all_targets()
            # rule removal
            if (transaction['ipdb_scope'] in ('shadow', 'remove')) or\
                    ((transaction['ipdb_scope'] == 'create') and
                     commit_phase == 2):
                if transaction['ipdb_scope'] == 'shadow':
                    with self._direct_state:
                        self['ipdb_scope'] = 'locked'
                # create watchdog
                wd = self.ipdb.watchdog('RTM_DELRULE',
                                        priority=self['priority'])
                for rule in self.nl.rule('delete', **snapshot):
                    self.ipdb.rules.load_netlink(rule)
                wd.wait()
                if transaction['ipdb_scope'] == 'shadow':
                    with self._direct_state:
                        self['ipdb_scope'] = 'shadow'

        except Exception as e:
            if devop == 'add':
                error = e
                self.nl = None
                self['ipdb_scope'] = 'invalid'
                del self.ipdb.rules[self.make_key(self)]
            elif commit_phase == 1:
                ret = self.commit(transaction=snapshot,
                                  commit_phase=2,
                                  commit_mask=commit_mask)
                if isinstance(ret, Exception):
                    error = ret
                else:
                    error = e
            else:
                if drop:
                    self.drop(transaction.uid)
                x = RuntimeError()
                x.cause = e
                raise x

        if drop and commit_phase == 1:
            self.drop(transaction.uid)

        if error is not None:
            error.transaction = transaction
            raise error

        return self

    def remove(self):
        self['ipdb_scope'] = 'remove'
        return self

    def shadow(self):
        self['ipdb_scope'] = 'shadow'
        return self


class RulesDict(dict):

    def __init__(self, ipdb):
        self.ipdb = ipdb
        self.lock = threading.Lock()
        self._event_map = {'RTM_NEWRULE': self.load_netlink,
                           'RTM_DELRULE': self.load_netlink}

    def _register(self):
        for msg in self.ipdb.nl.get_rules():
            self.load_netlink(msg)

    def __getitem__(self, key):
        with self.lock:
            if isinstance(key, RuleKey):
                return super(RulesDict, self).__getitem__(key)
            elif isinstance(key, tuple):
                return super(RulesDict, self).__getitem__(RuleKey(*key))
            elif isinstance(key, int):
                for k in self.keys():
                    if key == k[2]:
                        return super(RulesDict, self).__getitem__(k)
            elif isinstance(key, dict):
                for v in self.values():
                    for k in key:
                        if key[k] != v.get(k, None):
                            break
                    else:
                        return v

    def add(self, spec=None, **kwarg):
        '''
        Create a rule from a dictionary
        '''
        spec = dict(spec or kwarg)
        rule = Rule(self.ipdb)
        rule.update(spec)
        # action and priority are parts of the key, so
        # they must be specified
        if 'priority' not in spec:
            spec['priority'] = 32000
        if 'table' in spec:
            spec['action'] = FR_ACT_NAMES['FR_ACT_TO_TBL']
        elif 'goto' in spec:
            spec['action'] = FR_ACT_NAMES['FR_ACT_GOTO']
        # setup the scope
        with rule._direct_state:
            rule['ipdb_scope'] = 'create'
        #
        rule.begin()
        for (key, value) in spec.items():
            rule[key] = value
        self[rule.make_key(spec)] = rule
        return rule

    def load_netlink(self, msg):

        if not isinstance(msg, fibmsg):
            return

        key = Rule.make_key(msg)

        # RTM_DELRULE
        if msg['event'] == 'RTM_DELRULE':
            try:
                # locate the record
                record = self[key]
                # delete the record
                if record['ipdb_scope'] not in ('locked', 'shadow'):
                    del self[key]
                    with record._direct_state:
                        record['ipdb_scope'] = 'detached'
            except Exception as e:
                # just ignore this failure for now
                log.debug("delrule failed for %s", e)
            return

        # RTM_NEWRULE
        if key not in self:
            self[key] = Rule(self.ipdb)
        self[key].load_netlink(msg)
        return self[key]


spec = [{'name': 'rules',
         'class': RulesDict,
         'kwarg': {}}]
