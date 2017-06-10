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
               ('RLINK_ATTR_DATA', 'asciiz'),
               ('RLINK_ATTR_LEN', 'uint32'))


class Rlink(GenericNetlinkSocket):

    def send_data(self, data):
        msg = rcmd()
        msg['cmd'] = RLINK_CMD_REQ
        msg['version'] = 1
        msg['attrs'] = [('RLINK_ATTR_DATA', data)]
        ret = self.nlm_request(msg,
                               self.prid,
                               msg_flags=NLM_F_REQUEST)[0]
        return ret.get_attr('RLINK_ATTR_LEN')


if __name__ == '__main__':
    try:
        # create protocol instance
        rlink = Rlink()
        rlink.bind('EXMPL_GENL', rcmd)
        # request a method
        print(rlink.send_data('x' * 65000))
    except:
        # if there was an error, log it to the console
        traceback.print_exc()
    finally:
        # finally -- release the instance
        rlink.close()
