.. _ndbinit:

NDB objects
===========

Start
-----

In the simplest case to start the DB is as easy as::

    ndb = NDB()

There are several debug options that may be useful:

* `log=<spec>` -- controls the logging
    * `log='off'` -- turn the logging off
    * `log='on'` or `log='stderr'` -- stdio/stderr logging
    * `log='syslog:facility'` -- log to syslog
    * `log=<url>` -- some other url that will be accepted by `logging`
* `rtnl_debug=<True|False>` -- create and use log tables to store RTNL events
* `libc=<obj>` -- NDB doesn't use libc, but may pass it to RTNL sources
* `sources={<spec>}` -- RTNL sources to use
* `db_provider=<spec>` -- which DB backend to use
* `db_spec=<spec>` -- this spec will be passed to the DB provider
* `auto_netns=<True|False>` -- [experimental] discover and connect to netns

rtnl_debug
~~~~~~~~~~

This option tell NDB if it must create and use the log tables. Normally
all the incoming events become aggregated, thus `RTM_NEWLINK` and `RTM_DELLINK`
will result in zero records -- an interface was created and destroyed.

But in the log tables all the records will be stored, so it is what it looks
like -- the events log. The log tables are not used to create objects, they
are not rotated. Use this option with caution.

To review the event logs use SQL or `ndb.schema.export()`

sources
~~~~~~~

The RTNL sources documenation: :ref:`ndbsources`

db_provider, db_spec
~~~~~~~~~~~~~~~~~~~~

The database backend options: :ref:`ndbschema`

Stop
----

In order to get all the pending calls finished and synchronized, it is
a good idea to explicitly close and stop the DB::

    ndb = NDB()
    ...
    ndb.close()
 
NDB objects also support the context manager protocol::

    with NDB() as ndb:
        ...
        ...
    #
    # ---> <--- here the NDB instance will be synchronized and stopped
