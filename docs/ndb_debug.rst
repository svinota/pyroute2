Debug and logging
=================

Logging
-------

A simple way to set up stderr logging::

   # to start logging on the DB init
   ndb = NDB(log='on')

   # ... or to start it in run time
   ndb.log('on')

   # ... the same as above, another syntax
   ndb.log.on

   # ... turn logging off
   ndb.log('off')

   # ... or
   ndb.log.off

It is possible also to set up logging to a file or to a syslog server::

   #
   ndb.log('file_name.log')

   #
   ndb.log('syslog://server:port')

Fetching DB data
----------------

By default, NDB starts with an in-memory SQLite3 database. In order to
perform post mortem analysis it may be more useful to start the DB with
a file DB or a PostgreSQL as the backend.

See more: :ref:`ndbschema`

RTNL events
-----------

All the loaded RTNL events may be stored in the DB. To turn that feature
on, one should start NDB with the `debug` option::

   ndb = NDB(debug=True)

The events may be downloaded later, e.g. before exit, with
`schema.export_debug()`::

   with NDB(log='on', debug=True) as ndb:
      # ... here some NDB operations
      ndb.schema.export_debug('ndb.schema')

Unlike ordinary table, limited with the number of network objects in the
system, the events log tables are not limited. Do not enable the events
logging in production, it may exhaust all the memory.

RTNL objects
------------

NDB creates RTNL objects on demand, it doesn't keep them all the time.
Weak references to all created objects are linked to the `ndb._rtnl_objects`
set::

   >>> [x for x in ndb._rtnl_objects]
   <weakref at 0x7f4296bf1a48; to 'Interface' at 0x7f4298465db0>
   <weakref at 0x7f4296bf1a98; to 'Interface' at 0x7f4298465678>

   >>> [type(x) for x in ndb._rtnl_objects]
   [<class 'weakref'>, <class 'weakref'>]

   >>> [type(x()) for x in ndb._rtnl_objects]
   [
      <class 'pyroute2.ndb.objects.interface.Interface'>,
      <class 'pyroute2.ndb.objects.interface.Interface'>
   ]

Object states
-------------

RTNL objects may be in several states:

   * invalid: the object does not exist in the system
   * system: the object exists both in the system and in NDB
   * setns: the existing object should be moved to another network namespace
   * remove: the existing object must be deleted from the system

The state transitions are logged in the state log::

   >>> from pyroute2 import NDB
   >>> ndb = NDB()
   >>> c = ndb.interfaces.create(ifname='t0', kind='dummy').commit()
   >>> c.state.events
   [
      (1557752212.6703758, 'invalid'),
      (1557752212.6821117, 'system')
   ]

The timestamps allow to correlate the state transitions with the
NDB log and the RTNL events log, in the case it was enabled.

Object snapshots
----------------

Before running any commit, NDB marks all the related records in the DB
with a random value in the `f_tflags` DB field (`tflags` object field),
and stores all the marked records in the snapshot tables. Shortly, the
`commit()` is a `snapshot() + apply() + revert() if failed`::

   >>> nic = ndb.interfaces['t0']
   >>> nic['state']
   'down'
   >>> nic['state'] = 'up'
   >>> snapshot = nic.snapshot()
   >>> ndb.schema.snapshots
   {
      'addresses_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'neighbours_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'routes_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'nh_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'p2p_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_bridge_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_bond_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_vlan_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_vxlan_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_gre_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_vrf_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_vti_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'ifinfo_vti6_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>,
      'interfaces_139736119707256': <weakref at 0x7f16d8391a98; to 'Interface' at 0x7f16d9c708e0>
   }
   >>> nic.apply()
   ...
   >>> nic['state']
   'up'
   >>> snapshot.apply(rollback=True)
   ...
   >>> nic['state']
   'down'

Or same::

   >>> nic = ndb.interfaces['t0']
   >>> nic['state']
   'down'
   >>> nic['state'] = 'up'
   >>> nic.commit()
   >>> nic['state']
   'up'
   >>> nic.rollback()
   >>> nic['state']
   'down'

These snapshot tables are the objects' state before the changes were applied.

