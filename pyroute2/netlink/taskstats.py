'''
TaskStats module
================

All that you should know about TaskStats, is that you should not
use it. But if you have to, ok::

    import os
    from pyroute2 import TaskStats
    ts = TaskStats()
    ts.get_pid_stat(os.getpid())

It is not implemented normally yet, but some methods are already
usable.
'''

from pyroute2.iocore import TimeoutError
from pyroute2.netlink import Marshal
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink.client import Netlink
from pyroute2.netlink.generic import nla
from pyroute2.netlink.generic import genlmsg
from pyroute2.netlink.generic import ctrlmsg

TASKSTATS_CMD_UNSPEC = 0      # Reserved
TASKSTATS_CMD_GET = 1         # user->kernel request/get-response
TASKSTATS_CMD_NEW = 2

NLMSG_MIN_TYPE = 0x10

GENL_NAMSIZ = 16    # length of family name
GENL_MIN_ID = NLMSG_MIN_TYPE
GENL_MAX_ID = 1023

GENL_ADMIN_PERM = 0x01
GENL_CMD_CAP_DO = 0x02
GENL_CMD_CAP_DUMP = 0x04
GENL_CMD_CAP_HASPOL = 0x08

#
# List of reserved static generic netlink identifiers:
#
GENL_ID_GENERATE = 0
GENL_ID_CTRL = NLMSG_MIN_TYPE

#
# Controller
#

CTRL_CMD_UNSPEC = 0x0
CTRL_CMD_NEWFAMILY = 0x1
CTRL_CMD_DELFAMILY = 0x2
CTRL_CMD_GETFAMILY = 0x3
CTRL_CMD_NEWOPS = 0x4
CTRL_CMD_DELOPS = 0x5
CTRL_CMD_GETOPS = 0x6
CTRL_CMD_NEWMCAST_GRP = 0x7
CTRL_CMD_DELMCAST_GRP = 0x8
CTRL_CMD_GETMCAST_GRP = 0x9  # unused


CTRL_ATTR_UNSPEC = 0x0
CTRL_ATTR_FAMILY_ID = 0x1
CTRL_ATTR_FAMILY_NAME = 0x2
CTRL_ATTR_VERSION = 0x3
CTRL_ATTR_HDRSIZE = 0x4
CTRL_ATTR_MAXATTR = 0x5
CTRL_ATTR_OPS = 0x6
CTRL_ATTR_MCAST_GROUPS = 0x7

CTRL_ATTR_OP_UNSPEC = 0x0
CTRL_ATTR_OP_ID = 0x1
CTRL_ATTR_OP_FLAGS = 0x2

CTRL_ATTR_MCAST_GRP_UNSPEC = 0x0
CTRL_ATTR_MCAST_GRP_NAME = 0x1
CTRL_ATTR_MCAST_GRP_ID = 0x2


class tcmd(genlmsg):
    nla_map = (('TASKSTATS_CMD_ATTR_UNSPEC', 'none'),
               ('TASKSTATS_CMD_ATTR_PID', 'uint32'),
               ('TASKSTATS_CMD_ATTR_TGID', 'uint32'),
               ('TASKSTATS_CMD_ATTR_REGISTER_CPUMASK', 'asciiz'),
               ('TASKSTATS_CMD_ATTR_DEREGISTER_CPUMASK', 'asciiz'))


class tstats(nla):
    pack = "struct"
    fields = (('version', 'H'),                           # 2
              ('ac_exitcode', 'I'),                       # 4
              ('ac_flag', 'B'),                           # 1
              ('ac_nice', 'B'),                           # 1 --- 10
              ('cpu_count', 'Q'),                         # 8
              ('cpu_delay_total', 'Q'),                   # 8
              ('blkio_count', 'Q'),                       # 8
              ('blkio_delay_total', 'Q'),                 # 8
              ('swapin_count', 'Q'),                      # 8
              ('swapin_delay_total', 'Q'),                # 8
              ('cpu_run_real_total', 'Q'),                # 8
              ('cpu_run_virtual_total', 'Q'),             # 8
              ('ac_comm', '32s'),                         # 32 +++ 112
              ('ac_sched', 'B'),                          # 1
              ('__pad', '3x'),                            # 1 --- 8 (!)
              ('ac_uid', 'I'),                            # 4  +++ 120
              ('ac_gid', 'I'),                            # 4
              ('ac_pid', 'I'),                            # 4
              ('ac_ppid', 'I'),                           # 4
              ('ac_btime', 'I'),                          # 4  +++ 136
              ('ac_etime', 'Q'),                          # 8  +++ 144
              ('ac_utime', 'Q'),                          # 8
              ('ac_stime', 'Q'),                          # 8
              ('ac_minflt', 'Q'),                         # 8
              ('ac_majflt', 'Q'),                         # 8
              ('coremem', 'Q'),                           # 8
              ('virtmem', 'Q'),                           # 8
              ('hiwater_rss', 'Q'),                       # 8
              ('hiwater_vm', 'Q'),                        # 8
              ('read_char', 'Q'),                         # 8
              ('write_char', 'Q'),                        # 8
              ('read_syscalls', 'Q'),                     # 8
              ('write_syscalls', 'Q'),                    # 8
              ('read_bytes', 'Q'),                        # ...
              ('write_bytes', 'Q'),
              ('cancelled_write_bytes', 'Q'),
              ('nvcsw', 'Q'),
              ('nivcsw', 'Q'),
              ('ac_utimescaled', 'Q'),
              ('ac_stimescaled', 'Q'),
              ('cpu_scaled_run_real_total', 'Q'))

    def decode(self):
        nla.decode(self)
        self['ac_comm'] = self['ac_comm'][:self['ac_comm'].find('\0')]


class taskstatsmsg(genlmsg):

    nla_map = (('TASKSTATS_TYPE_UNSPEC', 'none'),
               ('TASKSTATS_TYPE_PID', 'uint32'),
               ('TASKSTATS_TYPE_TGID', 'uint32'),
               ('TASKSTATS_TYPE_STATS', 'stats'),
               ('TASKSTATS_TYPE_AGGR_PID', 'aggr_pid'),
               ('TASKSTATS_TYPE_AGGR_TGID', 'aggr_tgid'))

    class stats(tstats):
        pass  # FIXME: optimize me!

    class aggr_id(nla):
        nla_map = (('TASKSTATS_TYPE_UNSPEC', 'none'),
                   ('TASKSTATS_TYPE_PID', 'uint32'),
                   ('TASKSTATS_TYPE_TGID', 'uint32'),
                   ('TASKSTATS_TYPE_STATS', 'stats'))

        class stats(tstats):
            pass

    class aggr_pid(aggr_id):
        pass

    class aggr_tgid(aggr_id):
        pass


class TaskStats(Netlink):

    marshal = Marshal

    def __init__(self):
        Netlink.__init__(self)
        # FIXME
        self.marshal.msg_map[GENL_ID_CTRL] = ctrlmsg
        self.prid = self.get_protocol_id('TASKSTATS')
        self.marshal.msg_map[self.prid] = taskstatsmsg

    def get_protocol_id(self, prid):
        msg = ctrlmsg()
        msg['cmd'] = CTRL_CMD_GETFAMILY
        msg['version'] = 1
        msg['attrs'].append(['CTRL_ATTR_FAMILY_NAME', prid])
        response = self.nlm_request(msg, GENL_ID_CTRL,
                                    msg_flags=NLM_F_REQUEST)[0]
        prid = [i[1] for i in response['attrs']
                if i[0] == 'CTRL_ATTR_FAMILY_ID'][0]
        return prid

    def get_pid_stat(self, pid):
        '''
        Get taskstats for a process. Pid should be an integer.
        '''
        msg = tcmd()
        msg['cmd'] = TASKSTATS_CMD_GET
        msg['version'] = 1
        msg['attrs'].append(['TASKSTATS_CMD_ATTR_PID', pid])
        return self.nlm_request(msg,
                                self.prid,
                                msg_flags=NLM_F_REQUEST)

    def _register_mask(self, cmd, mask):
        msg = tcmd()
        msg['cmd'] = TASKSTATS_CMD_GET
        msg['version'] = 1
        msg['attrs'].append([cmd, mask])
        try:
            # there is no response to this request
            self.nlm_request(msg,
                             self.prid,
                             msg_flags=NLM_F_REQUEST,
                             response_timeout=0.1)
        except TimeoutError:
            pass

    def register_mask(self, mask):
        '''
        Start the accounting for a processors by a mask. Mask is
        a string, e.g.::
            0,1 -- first two CPUs
            0-4,6-10 -- CPUs from 0 to 4 and from 6 to 10

        When the accounting is turned on, on can receive messages
        with get() routine.

        Though the kernel has a procedure, that cleans up accounting,
        when it is not used, it is recommended to run deregister_mask()
        before process exit.
        '''
        self.monitor(True)
        self._register_mask('TASKSTATS_CMD_ATTR_REGISTER_CPUMASK',
                            mask)

    def deregister_mask(self, mask):
        '''
        Stop the accounting.
        '''
        self.monitor(False)
        self._register_mask('TASKSTATS_CMD_ATTR_DEREGISTER_CPUMASK',
                            mask)
