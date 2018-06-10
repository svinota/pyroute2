Generators
----------

Problem
=======

Until 0.5.2 Pyroute2 collected all the responses in a list
and returned them at once. It may be ok as long as there is
not so many objects to return. But let's say there are some
thousands of routes::

    $ ip ro | wc -l
    315417

Now we use a script to retrieve the routes::

    import sys
    from pyroute2 import config
    from pyroute2 import IPRoute

    config.nlm_generator = (sys.argv[1].lower()
                            if len(sys.argv) > 1
                            else 'false') == 'true'

    with IPRoute() as ipr:
        for route in ipr.get_routes():
            pass

If the library collects all the routes in a list and returns
the list, it may take a lot of memory::

    $ /usr/bin/time -v python e.py false
        Command being timed: "python e.py false"
        User time (seconds): 30.42
        System time (seconds): 3.63
        Percent of CPU this job got: 99%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 0:34.09
        Average shared text size (kbytes): 0
        Average unshared data size (kbytes): 0
        Average stack size (kbytes): 0
        Average total size (kbytes): 0
        Maximum resident set size (kbytes): 2416472
        Average resident set size (kbytes): 0
        Major (requiring I/O) page faults: 0
        Minor (reclaiming a frame) page faults: 604787
        Voluntary context switches: 9
        Involuntary context switches: 688
        Swaps: 0
        File system inputs: 0
        File system outputs: 0
        Socket messages sent: 0
        Socket messages received: 0
        Signals delivered: 0
        Page size (bytes): 4096
        Exit status: 0

2416472 kbytes of RSS. Pretty much.

Solution
========

Now we use generator to iterate the results::

    $ /usr/bin/time -v python e.py true
        Command being timed: "python e.py true"
        User time (seconds): 18.48
        System time (seconds): 0.99
        Percent of CPU this job got: 99%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 0:19.49
        Average shared text size (kbytes): 0
        Average unshared data size (kbytes): 0
        Average stack size (kbytes): 0
        Average total size (kbytes): 0
        Maximum resident set size (kbytes): 45132
        Average resident set size (kbytes): 0
        Major (requiring I/O) page faults: 0
        Minor (reclaiming a frame) page faults: 433589
        Voluntary context switches: 9
        Involuntary context switches: 244
        Swaps: 0
        File system inputs: 0
        File system outputs: 0
        Socket messages sent: 0
        Socket messages received: 0
        Signals delivered: 0
        Page size (bytes): 4096
        Exit status: 0

45132 kbytes of RSS. That's the difference. Say we have a bit more
routes::

    $ ip ro | wc -l
    678148

Without generators the script will simply run ot of memory. But with
the generators::

    $ /usr/bin/time -v python e.py true
        Command being timed: "python e.py true"
        User time (seconds): 39.63
        System time (seconds): 2.78
        Percent of CPU this job got: 99%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 0:42.75
        Average shared text size (kbytes): 0
        Average unshared data size (kbytes): 0
        Average stack size (kbytes): 0
        Average total size (kbytes): 0
        Maximum resident set size (kbytes): 45324
        Average resident set size (kbytes): 0
        Major (requiring I/O) page faults: 0
        Minor (reclaiming a frame) page faults: 925560
        Voluntary context switches: 11
        Involuntary context switches: 121182
        Swaps: 0
        File system inputs: 0
        File system outputs: 0
        Socket messages sent: 0
        Socket messages received: 0
        Signals delivered: 0
        Page size (bytes): 4096
        Exit status: 0

Again, 45324 kbytes of RSS.

Configuration
=============

To turn the generator option on, one should set ``pyroute2.config.nlm_generator``
to ``True``. By default is ``False`` not to break existing projects.::

    from pyroute2 import config
    from pyroute2 import IPRoute
    
    config.nlm_generator = True
    with IPRoute() as ipr:
        for route in ipr.get_routes():
            handle(route)

IPRoute and generators
======================

IPRoute objects will return generators only for methods that employ ``GET_...``
requests like ``get_routes()``, ``get_links()``, ``link('dump', ...)``, ``addr('dump', ...)``.
Setters will work as usually to apply changes immediately.
