#!/usr/bin/env python

import traceback
from pprint import pprint
from pyroute2.netlink.generic import GenericNetlinkSocket

if __name__ == '__main__':
    try:
        # create protocol instance
        genl = GenericNetlinkSocket(ext_ack=True)

        # extract policy
        msg = genl.policy('nlctrl')

        # dump policy information
        pprint(msg)
    except:
        # if there was an error, log it to the console
        traceback.print_exc()
    finally:
        # finally -- release the instance
        genl.close()
