from pyroute2.netlink import NLMSG_DONE
from pyroute2.netlink.nlsocket import Marshal

from . import ConnectorSocket, cn_msg

CN_IDX_PROC = 0x1

PROC_EVENT_NONE = 0x0
PROC_EVENT_FORK = 0x1
PROC_EVENT_EXEC = 0x2
PROC_EVENT_UID = 0x4
PROC_EVENT_GID = 0x40
PROC_EVENT_SID = 0x80
PROC_EVENT_PTRACE = 0x100
PROC_EVENT_COMM = 0x200
PROC_EVENT_COREDUMP = 0x40000000
PROC_EVENT_EXIT = 0x80000000

CN_IDX_PROC = 0x1
CN_VAL_PROC = 0x1

PROC_CN_MCAST_LISTEN = 0x1
PROC_CN_MCAST_IGNORE = 0x2


class proc_event_base(cn_msg):

    fields = cn_msg.fields + (
        ('what', 'I'),
        ('cpu', 'I'),
        ('timestamp_ns', 'Q'),
    )


class proc_event_control(cn_msg):

    fields = cn_msg.fields + (('action', 'I'),)


class ProcEventMarshal(Marshal):

    key_format = 'I'
    key_offset = 36
    msg_map = {
        PROC_EVENT_NONE: proc_event_base,
        PROC_EVENT_FORK: proc_event_base,
        PROC_EVENT_EXEC: proc_event_base,
        PROC_EVENT_UID: proc_event_base,
        PROC_EVENT_GID: proc_event_base,
        PROC_EVENT_SID: proc_event_base,
        PROC_EVENT_PTRACE: proc_event_base,
        PROC_EVENT_COMM: proc_event_base,
        PROC_EVENT_COREDUMP: proc_event_base,
        PROC_EVENT_EXIT: proc_event_base,
    }


class ProcEventSocket(ConnectorSocket):
    def __init__(self, fileno=None):
        super().__init__(fileno=fileno)
        self.marshal = ProcEventMarshal()

    def bind(self):
        return super().bind(groups=CN_IDX_PROC)

    def control(self, listen):
        msg = proc_event_control()
        msg['action'] = (
            PROC_CN_MCAST_LISTEN if listen else PROC_CN_MCAST_IGNORE
        )
        msg['idx'] = CN_IDX_PROC
        msg['val'] = CN_VAL_PROC
        msg['len'] = 4  # FIXME payload length calculation
        msg_type = NLMSG_DONE
        self.put(msg, msg_type, msg_flags=0, msg_seq=0)
        return tuple(self.get(msg_seq=-1))
