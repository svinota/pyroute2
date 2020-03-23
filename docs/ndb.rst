.. ndb:

NDB module
==========

NDB is a high level network management module. IT allows to manage interfaces,
routes, addresses etc. of connected systems, containers and network
namespaces.

In a nuthsell, NDB collects and aggregates netlink events in an SQL database,
provides Python objects to reflect the system state, and applies changes back
to the system. The database expects updates only from the sources, no manual
SQL updates are expected normally.

.. aafig::
    :scale: 80
    :textual:

        +----------------------------------------------------------------+
      +----------------------------------------------------------------+ |
    +----------------------------------------------------------------+ | |
    |                                                                | | |
    |                              kernel                            | |-+
    |                                                                |-+
    +----------------------------------------------------------------+
            |                      | ^                     | ^
            | `netlink events`     | |                     | |
            | `inotify events`     | |                     | |
            | `...`                | |                     | |
            v                      v |                     v |
     +--------------+        +--------------+        +--------------+
     |     source   |        |     source   |        |     source   |<--\
     +--------------+        +--------------+        +--------------+   |
            |                       |                       |           |
            |                       |                       |           |
            \-----------------------+-----------------------/           |
                                    |                                   |
              parsed netlink events | `NDB._event_queue`                |
                                    |                                   |
                                    v                                   |
                        +------------------------+                      |
                        | `NDB.__dbm__()` thread |                      |
                        +------------------------+                      |
                                    |                                   |
                                    v                                   |
                     +-----------------------------+                    |
                     | `NDB.schema.load_netlink()` |                    |
                     | `NDB.objects.*.load*()`     |                    |
                     +-----------------------------+                    |
                                    |                                   |
                                    v                                   |
                         +----------------------+                       |
                         |  SQL database        |                       |
                         |     `SQLite`         |                       |
                         |     `PostgreSQL`     |                       |
                         +----------------------+                       |
                                    |                                   |
                                    |                                   |
                                    V                                   |
                              +---------------+                         |
                            +---------------+ |                         |
                          +---------------+ | |  `RTNL_Object.apply()`  |
                          | NDB object:   | | |-------------------------/
                          |  `interface`  | | |
                          |  `address`    | | |
                          |  `route`      | |-+
                          |  `...`        |-+
                          +---------------+


NDB can work with remote systems via ssh, in that case
`mitogen <https://github.com/dw/mitogen>`_ module is required. It is
possible to connect also OpenBSD and FreeBSD systems, but in read-only
mode for now.

.. automodule:: pyroute2.ndb.main

Reference
---------

.. toctree::
   :maxdepth: 2

   ndb_objects
   ndb_reports
   ndb_interfaces
   ndb_addresses
   ndb_routes
   ndb_schema
   ndb_sources
   ndb_debug

*work in progress*
