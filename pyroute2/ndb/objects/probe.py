from pyroute2.netlink.rtnl.probe_msg import probe_msg

from ..objects import RTNL_Object


def load_probe_msg(schema, target, event):
    pass


schema = probe_msg.sql_schema().unique_index()
init = {
    'specs': [['probe', schema]],
    'classes': [['probe', probe_msg]],
    'event_map': {probe_msg: [load_probe_msg]},
}


class Probe(RTNL_Object):

    table = 'probe'
    msg_class = probe_msg
    api = 'probe'

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = probe_msg
        self.event_map = {probe_msg: 'load_probe_msg'}
        super().__init__(*argv, **kwarg)

    def check(self):
        return True
