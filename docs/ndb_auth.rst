.. _ndbauth:

Authorization plugins
=====================

.. automodule:: pyroute2.ndb.auth_manager

Usecase: OpenStack Keystone auth
--------------------------------

Say we have a public service that provides access to NDB instance via
HTTP, and authenticates users via Keystone. Then the auth flow could be:

1. Accept a connection from a client
2. Create custom auth manager object A
3. A.__init__() validates X-Auth-Token against Keystone (Authentication)
4. A.check() checks that X-Auth-Token is not expired (Authorization)
5. The auth result is being logged (Accounting)

An example AuthManager with OpenStack APIv3 support you may find in the
`/examples/ndb/` directory.

.. literalinclude:: ../examples/ndb/keystone_auth.py
   :language: python
   :caption: keystone_auth.py
   :name: keystone_auth

Usecase: RADIUS auth
--------------------

.. literalinclude:: ../examples/ndb/radius_auth.py
   :language: python
   :caption: radius_auth.py
   :name: radius_auth
