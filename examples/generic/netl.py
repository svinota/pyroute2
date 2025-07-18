#!/usr/bin/env python3

from pyroute2.netlink import NLM_F_REQUEST, genlmsg
from pyroute2.netlink.generic import GenericNetlinkSocket

EXMPL_CMD_UNSPEC = 0
EXMPL_CMD_ECHO = 1


class rcmd(genlmsg):
    '''
    Message class that will be used to communicate
    with the kernel module
    '''

    nla_map = (('EXMPL_NLA_UNSPEC', 'none'), ('EXMPL_NLA_STR', 'asciiz'))


class Exmpl(GenericNetlinkSocket):
    def send_data(self, data):
        msg = rcmd()
        msg['cmd'] = EXMPL_CMD_ECHO
        msg['version'] = 1
        msg['attrs'] = [('EXMPL_NLA_STR', data)]
        ret = self.nlm_request(msg, self.prid, msg_flags=NLM_F_REQUEST)[0]
        return ret.get_attr('EXMPL_NLA_STR')


if __name__ == '__main__':
    with Exmpl() as exmpl:
        exmpl.bind('ECHO_GENL', rcmd)
        print(exmpl.send_data('hello world'))
