.. _ndbinit:

NDB objects
===========

Start
-----

In the simplest case to start the DB is as easy as::

    ndb = NDB()

There are several debug options that may be useful:

* `log=<spec>` -- controls the logging
* `rtnl_debug=<True|False>` -- create and use log tables to store RTNL events
* `libc=<obj>` -- NDB doesn't use libc, but may pass it to RTNL sources
* `sources={<spec>}` -- RTNL sources to use
* `db_provider=<spec>` -- which DB backend to use
* `db_spec=<spec>` -- this spec will be passed to the DB provider
* `auto_netns=<True|False>` -- [experimental] discover and connect to netns

Some options explained:

log
~~~

The simplest case is `log='on'`, it turns on stdio logging.

More log alternatives: :ref:`ndbdebug`

rtnl_debug
~~~~~~~~~~

This option tell NDB if it must create and use the log tables. Normally
all the incoming events become aggregated, thus `RTM_NEWLINK` and `RTM_DELLINK`
will result in zero records -- an interface was created and destroyed.

But in the log tables all the records will be stored, so it is what it looks
like -- the events log. The log tables are not used to create objects, they
are not rotated. Use this option with caution.

To review the event logs use SQL or `ndb.schema.export()`

See also: :ref:`ndbdebug`

sources
~~~~~~~

::
    >>> sources = [{'netns': 'test01'},
                   {'netns': 'test02'},
                   {'target': 'localhost', 'kind': 'local'}]
    >>> ndb = NDB(log='on', sources=sources)
    2020-03-24 18:01:48,241    DEBUG pyroute2.ndb.139900805197264.sources.test01: init
    2020-03-24 18:01:48,242    DEBUG pyroute2.ndb.139900805197264.sources.test01: starting the source
    2020-03-24 18:01:48,242    DEBUG pyroute2.ndb.139900805197264.sources.test02: init
    2020-03-24 18:01:48,243    DEBUG pyroute2.ndb.139900805197264.sources.test01: connecting
    2020-03-24 18:01:48,248    DEBUG pyroute2.ndb.139900805197264.sources.test02: starting the source
    2020-03-24 18:01:48,249    DEBUG pyroute2.ndb.139900805197264.sources.localhost: init
    2020-03-24 18:01:48,250    DEBUG pyroute2.ndb.139900805197264.sources.test02: connecting
    2020-03-24 18:01:48,256    DEBUG pyroute2.ndb.139900805197264.sources.localhost: starting the source
    2020-03-24 18:01:48,259    DEBUG pyroute2.ndb.139900805197264.sources.localhost: connecting
    2020-03-24 18:01:48,262    DEBUG pyroute2.ndb.139900805197264.sources.localhost: loading
    2020-03-24 18:01:48,265    DEBUG pyroute2.ndb.139900805197264.sources.test01: loading
    2020-03-24 18:01:48,278    DEBUG pyroute2.ndb.139900805197264.sources.test02: loading
    2020-03-24 18:01:48,478    DEBUG pyroute2.ndb.139900805197264.sources.localhost: running
    2020-03-24 18:01:48,499    DEBUG pyroute2.ndb.139900805197264.sources.test01: running
    2020-03-24 18:01:48,537    DEBUG pyroute2.ndb.139900805197264.sources.test02: running


The RTNL sources documenation: :ref:`ndbsources`

db_provider, db_spec
~~~~~~~~~~~~~~~~~~~~

::
    >>> ndb_fs = NDB(db_provider='sqlite3', db_spec='test.db')
    ...
    $ echo 'select f_ifla_ifname from interfaces' | sqlite3 test.db
    lo
    enp0s31f6
    wlp58s0
    virbr0
    virbr0-nic
    ...


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
