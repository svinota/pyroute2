import logging
from pyroute2.netlink.rtnl.fibmsg import fibmsg
from pyroute2.ipdb.transactional import Transactional

logging.basicConfig()
log = logging.getLogger('pyroute2.ipdb.route')


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

    def commit(self, tid=None, transaction=None, rollback=False):
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

                self.nl.rule(devop, **transaction)
                transaction.wait_all_targets()
            # rule removal
            if (transaction['ipdb_scope'] in ('shadow', 'remove')) or\
                    ((transaction['ipdb_scope'] == 'create') and rollback):
                if transaction['ipdb_scope'] == 'shadow':
                    with self._direct_state:
                        self['ipdb_scope'] = 'locked'
                # create watchdog
                wd = self.ipdb.watchdog('RTM_DELRULE',
                                        priority=self['priority'])
                for rule in self.nl.rule('delete', **snapshot):
                    self.ipdb._rule_del(rule)
                wd.wait()
                if transaction['ipdb_scope'] == 'shadow':
                    with self._direct_state:
                        self['ipdb_scope'] = 'shadow'

        except Exception as e:
            if devop == 'add':
                error = e
                self.nl = None
                self['ipdb_scope'] = 'invalid'
                del self.ipdb.rules.idx[self['priority']]
            elif not rollback:
                ret = self.commit(transaction=snapshot, rollback=True)
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

        if drop and not rollback:
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


class RuleSet(dict):

    def __init__(self, ipdb):
        self.ipdb = ipdb

    def add(self, spec=None, **kwarg):
        '''
        Create a route from a dictionary
        '''
        spec = dict(spec or kwarg)
        if 'priority' not in spec:
            raise ValueError('priority not specified')

        rule = Rule(self.ipdb)
        rule.update(spec)
        with rule._direct_state:
            rule['ipdb_scope'] = 'create'
        rule.begin()
        for (key, value) in spec.items():
            rule[key] = value
        self[spec['prioriy']] = rule
        return rule

    def load_netlink(self, msg):
        '''
        Loads an existing route from a rtmsg
        '''
        if not isinstance(msg, fibmsg):
            return

        priority = msg.get_attr('FRA_PRIORITY') or 0

        # RTM_DELRULE
        if msg['event'] == 'RTM_DELRULE':
            try:
                # locate the record
                record = self[priority]
                # delete the record
                if record['ipdb_scope'] not in ('locked', 'shadow'):
                    del self[priority]
                    with record._direct_state:
                        record['ipdb_scope'] = 'detached'
            except Exception as e:
                # just ignore this failure for now
                log.debug("delroute failed for %s", e)
            return

        # RTM_NEWRULE
        self[priority] = Rule(self.ipdb).load_netlink(msg)
        return self[priority]
