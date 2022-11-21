'''
:test:argv:testing
:test:argv:secret
:test:environ:RADIUS_SERVER=127.0.0.1
:test:environ:RADIUS_SECRET=secret

An example of using RADIUS authentication with NDB.

In order to run the example you can setup a FreeRADIUS server::

    # /etc/raddb/clients
    client test {
        ipaddr = 192.168.122.101  # IP addr of your client
        secret = s3cr3t
    }

    # /etc/raddb/users
    testing Cleartext-Password := "secret"

Then setup your client::

    # download RADIUS dictionaries
    $ export GITSERVER=https://raw.githubusercontent.com
    $ export DICTPATH=pyradius/pyrad/master/example
    $ wget $GITSERVER/$DICTPATH/dictionary
    $ wget $GITSERVER/$DICTPATH/dictionary.freeradius

    # setup the environment
    $ cat radius.rc
    export RADIUS_SERVER=192.168.122.1
    export RADIUS_SECRET=s3cr3t
    export PYTHONPATH=`pwd`

    $ . radius.rc
    $ python examples/ndb/radius_auth.py testing secret

'''

import os
import sys
from pyrad.client import Client
from pyrad.dictionary import Dictionary
import pyrad.packet
from pyroute2 import NDB


class RadiusAuthManager(object):
    def __init__(self, user, password, log):
        client = Client(
            server=os.environ.get('RADIUS_SERVER'),
            secret=os.environ.get('RADIUS_SECRET').encode('ascii'),
            dict=Dictionary('dictionary'),
        )
        req = client.CreateAuthPacket(
            code=pyrad.packet.AccessRequest, User_Name=user
        )
        req['User-Password'] = req.PwCrypt(password)
        reply = client.SendPacket(req)
        self.auth = reply.code
        self.log = log

    def check(self, obj, tag):
        #
        self.log.info('%s access' % (tag,))
        return self.auth == pyrad.packet.AccessAccept


with NDB(log='debug') as ndb:
    # create a utility log channel
    log = ndb.log.channel('main')

    # create an AuthManager-compatible object
    log.info('request radius auth')
    am = RadiusAuthManager(sys.argv[1], sys.argv[2], ndb.log.channel('radius'))
    log.info('radius auth complete')

    # create an auth proxy for these credentials
    ap = ndb.auth_proxy(am)

    # validate access via that proxy
    print(ap.interfaces['lo'])
