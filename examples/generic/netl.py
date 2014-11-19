#!/usr/bin/env python

import traceback
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import genlmsg
from pyroute2.netlink.generic import GenericNetlinkSocket


RLINK_CMD_UNSPEC = 0
RLINK_CMD_REQ = 1


class rcmd(genlmsg):
    '''
    Message class that will be used to communicate
    with the kernel module
    '''
    nla_map = (('RLINK_ATTR_UNSPEC', 'none'),
               ('RLINK_ATTR_DATA', 'asciiz'))


class Rlink(GenericNetlinkSocket):
    '''
    Custom generic netlink protocol. Has one method,
    `hello_world()`, the only netlink call of the kernel
    module.
    '''
    def hello_world(self):
        msg = rcmd()
        msg['cmd'] = RLINK_CMD_REQ
        msg['version'] = 1
        ret = self.nlm_request(msg,
                               self.prid,
                               msg_flags=NLM_F_REQUEST)[0]
        return ret.get_attr('RLINK_ATTR_DATA')

try:
    # create protocol instance
    rlink = Rlink()
    rlink.bind('EXMPL_GENL', rcmd)
    # request a method
    print(rlink.hello_world())
except:
    # if there was an error, log it to the console
    traceback.print_exc()
finally:
    # finally -- release the instance
    rlink.close()
