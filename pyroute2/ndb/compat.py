def ipdb_interfaces_view(ndb):
    '''Provide read-only interfaces view with IPDB layout.

    In addition to standard NDB fields provides some IPDB
    specific fields.

    The method returns a simple dict structure, no background
    updates or system changes are supported.

    Please open a ticket on the project page if you are
    missing any attribute used in your project:

    https://github.com/svinota/pyroute2/issues
    '''
    ret = {}

    for record in ndb.interfaces.dump():
        interface = record._as_dict()
        interface['ipdb_scope'] = 'system'
        interface['ipdb_priority'] = 0
        interface['ipaddr'] = tuple(
            (
                (x.address, x.prefixlen)
                for x in (ndb.addresses.dump().filter(index=record.index))
            )
        )
        interface['ports'] = tuple(
            (
                x.index
                for x in (ndb.interfaces.dump().filter(master=record.index))
            )
        )
        interface['neighbours'] = tuple(
            (
                x.dst
                for x in (ndb.neighbours.dump().filter(ifindex=record.index))
            )
        )
        ret[record.ifname] = interface

    return ret
