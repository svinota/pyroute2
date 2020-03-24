.. _choice:

IPRoute or NDB
--------------

There are two different modules in the library, working on different
abstraction levels and employing different approaches. But since they
may be used to solve similar tasks, here is a short comparison that
should help you to make the choice.

:ref:`iproute`

    * Decent coverage of the kernel functionality
    * Supports TC
    * No service threads by default
    * No additional Python objects to represent RTNL objects
    * Low-level API
    * No RTNL objects state synchronisation
    * Works only with one RTNL source

:ref:`ndb`

    * Only a subset of RTNL functionality
    * Doesn't support TC
    * Thread-based architecture
    * Creates Python objects to reflect RTNL objects: may consume a lot of memory
    * High-level API with state synchroniztion
    * Objects state integrity
    * Objects relations
    * Aggregates multiple RTNL sources -- systems, netns etc.

While IPRoute provides better RTNL functionality coverage, it operates on
a different level than NDB. IPRoute is a plain 1-to-1 mapping of the
kernel RTNL API calls and notifications. You have to know the message
structure and the notifications order to reconstruct the system state.
IRPoute calls return as soon as the response from the kernel arrives,
but it doesn't mean that requested changes are already applied.

NDB provides a more user-friendly API that monitors notifications and
aggregates them, ensures RTNL objects state integrity. Creating an
interface you can be sure that the `commit()` call returns only when
the interface gets really created. Long-running NDB instance also
provides better performance since it doesn't list the system objects
but accumulates the info from RTNL notifications. It comes at the cost
of the memory and the code complexity.

Shortly summarized, use **IPRoute** for

    * For one-shot scripts
    * When the RTNL objects relations are not important
    * When there's no need to synchronize states
    * When threads are not an option

**NDB**, on the other hand, is better:

    * For long-running programs
    * To build more user-friendly environments
    * When states and relations should be ensured and synchronized
