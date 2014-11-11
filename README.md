pyroute2
========

Pyroute2 is a pure Python netlink library. It requires only
Python stdlib, no 3rd party libraries. Later it can change,
but the deps tree will remain as simple, as it is possible.

The library contains all you need to build either one-node,
or distributed netlink-related solutions. It consists of two
major parts:

* Netlink protocol implementations.
* Messaging infrastructure: broker, clients, etc.

rtnetlink sample
----------------

More samples you can read in the project documentation.
The lowest possible layer, simple socket interface. This
socket supports normal socket API and can be used in
poll/select::

    from pyroute2 import IPRSocket

    # create the socket
    ip = IPRSocket()

    # bind
    ip.bind()

    # get and parse a broadcast message
    ip.get()

    # close
    ip.close()


Low-level iproute utility. The utility uses implicit
threads, so notice `ip.release()` call -- it is required
to sync threads before exit::

    from pyroute2 import IPRoute

    # get access to the netlink socket
    ip = IPRoute()

    # print interfaces
    print ip.get_links()

    # stop working with netlink and release all sockets
    ip.release()


High-level transactional interface, IPDB, `release()`
call is also required::

    from pyroute2 import IPDB
    # local network settings
    ip = IPDB()
    # create bridge and add ports and addresses
    # transaction will be started with `with` statement
    # and will be committed at the end of the block
    try:
        with ip.create(kind='bridge', ifname='rhev') as i:
            i.add_port(ip.interfaces.em1)
            i.add_port(ip.interfaces.em2)
            i.add_ip('10.0.0.2/24')
    except Exception as e:
        print(e)
    finally:
        ip.release()


The project contains several modules for different types of
netlink messages, not only RTNL.

installation
------------

`make install` or `pip install pyroute2`

requires
--------

Python >= 2.6

  * test reqs (optional): **python-coverage**, **python-nose**

links
-----

* home: https://github.com/svinota/pyroute2
* bugs: https://github.com/svinota/pyroute2/issues
* pypi: https://pypi.python.org/pypi/pyroute2
* docs: http://docs.pyroute2.org/
* list: https://groups.google.com/d/forum/pyroute2-dev
