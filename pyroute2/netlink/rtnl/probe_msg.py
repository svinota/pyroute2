from pyroute2.netlink import nlmsg


class probe_msg(nlmsg):
    '''
    Fake message type to represent network probe info.

    This is a prototype, the NLA layout is subject to change without
    notification.
    '''

    __slots__ = ()
    prefix = 'PROBE_'

    fields = (
        ('family', 'B'),
        ('proto', 'B'),
        ('port', 'H'),
        ('dst_len', 'I'),
        ('cmd', 'I'),
    )

    nla_map = (
        ('PROBE_UNSPEC', 'none'),
        ('PROBE_KIND', 'asciiz'),
        ('PROBE_STDOUT', 'asciiz'),
        ('PROBE_STDERR', 'asciiz'),
        ('PROBE_SRC', 'target'),
        ('PROBE_DST', 'target'),
    )
