pyroute2
========

Pyroute2 is a pure Python netlink and messaging library. It
requires only Python stdlib, no 3rd party libraries. Later
it can change, but the deps tree will remain as simple, as
it is possible.

The library contains all you need to build either one-node,
or distributed netlink-related solutions. It consists of two
major parts:

* Netlink parsers: NETLINK\_ROUTE, TASKSTATS, etc.
* Messaging infrastructure: broker, clients, etc.

RTNETLINK sample
----------------

More samples you can read in the project documentation.
Low-level interface::

    from pyroute2 import IPRoute

    # get access to the netlink socket
    ip = IPRoute()

    # print interfaces
    print ip.get_links()

    # stop working with netlink and release all sockets
    ip.release()

High-level transactional interface, IPDB::

    from pyroute2 import IPDB
    # local network settings
    ip = IPDB()
    # create bridge and add ports and addresses
    # transaction will be started with `with` statement
    # and will be committed at the end of the block
    with ip.create(kind='bridge', ifname='rhev') as i:
        i.add_port(ip.em1)
        i.add_port(ip.em2)
        i.add_ip('10.0.0.2/24')


The project contains several modules for different types of
netlink messages, not only RTNL.

messaging sample
----------------

Server side::

    from pyroute2.rpc import Node
    from pyroute2.rpc import public


    class Namespace(object):

        @public
        def echo(self, msg):
            return '%s passed' % (msg)

    node = Node()
    node.register(Namespace())
    node.serve('tcp://localhost:9824')

    # wait for exit -- activity will be done in the
    # background thread
    raw_input(' hit return to exit >> ')

Client side::

    from pyroute2.rpc import Node

    node = Node()
    proxy = node.connect('tcp://localhost:9824')
    print(proxy.echo('test'))


It will print out `test passed`.

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
* docs: http://peet.spb.ru/pyroute2/
* list: https://groups.google.com/d/forum/pyroute2-dev
