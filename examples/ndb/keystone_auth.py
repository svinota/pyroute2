'''
:test:argv:14080769fe05e1f8b837fb43ca0f0ba4

A simplest example of a custom AuthManager and its usage
with `AuthProxy` objects.

Here we authenticate the auth token against Keystone and
allow any NDB operations until it is expired.

One can get such token with a curl request::

    $ cat request.json
    { "auth": {
        "identity": {
          "methods": ["password"],
          "password": {
            "user": {
              "name": "admin",
              "domain": { "name": "admin_domain" },
              "password": "secret"
            }
          }
        },
        "scope": {
          "project": {
            "id": "f0af12d451fb4bccbb38217e7f9afe9a"
          }
        }
      }
    }

    $ curl -i \
            -H "Content-Type: application/json" \
            -d "@request.json" \
            http://keystone:5000/v3/auth/tokens

`X-Subject-Token` header in the response will be the token we need. Say we
get `14080769fe05e1f8b837fb43ca0f0ba4` as `X-Subject-Token`. Then you can
run::

    $ . openstack.rc  # <-- your OpenStack APIv3 RC file
    $ export PYTHONPATH=`pwd`
    $ python examples/ndb/keystone_auth.py 14080769fe05e1f8b837fb43ca0f0ba4

Using this example you can implement services that export NDB via any RPC,
e.g. HTTP, and use Keystone integration. Same scheme may be used for any
other Auth API, be it RADIUS or like that.

An example of a simple HTTP service you can find in /cli/pyroute2-cli.
'''

import os
import sys
import time
from dateutil.parser import parse as isodate
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client as ksclient
from keystoneclient.v3.tokens import TokenManager
from pyroute2 import NDB


class OSAuthManager(object):
    def __init__(self, token, log):
        # create a Keystone password object
        auth = v3.Password(
            auth_url=os.environ.get('OS_AUTH_URL'),
            username=os.environ.get('OS_USERNAME'),
            password=os.environ.get('OS_PASSWORD'),
            user_domain_name=(os.environ.get('OS_USER_DOMAIN_NAME')),
            project_id=os.environ.get('OS_PROJECT_ID'),
        )
        # create a session object
        sess = session.Session(auth=auth)
        # create a token manager
        tmanager = TokenManager(ksclient.Client(session=sess))
        # validate the token
        keystone_response = tmanager.validate(token)
        # init attrs
        self.log = log
        self.expire = isodate(keystone_response['expires_at']).timestamp()

    def check(self, obj, tag):
        #
        # totally ignore obj and tag, validate only token expiration
        #
        # problems to be solved before you use this code in production:
        # 1. access levels: read-only, read-write -- match tag
        # 2. how to deal with revoked tokens
        #
        if time.time() > self.expire:
            self.log.error('%s permission denied' % (tag,))
            raise PermissionError('keystone token has been expired')

        self.log.info('%s permission granted' % (tag,))
        return True


with NDB(log='debug') as ndb:
    # create a utility log channel
    log = ndb.log.channel('main')

    # create an AuthManager-compatible object
    log.info('request keystone auth')
    am = OSAuthManager(sys.argv[1], ndb.log.channel('keystone'))
    log.info('keystone auth complete, expires %s' % am.expire)

    # create an auth proxy for this particular token
    ap = ndb.auth_proxy(am)

    # validate access via that proxy
    print(ap.interfaces['lo'])
