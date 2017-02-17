'''
IPSet module
============

ipset support.

This module is tested with hash:ip, hash:net, list:set and several
other ipset structures (like hash:net,iface). There is no guarantee
that this module is working with all available ipset modules.

It supports almost all kernel commands (create, destroy, flush,
rename, swap, test...)
'''
import errno
import socket
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_EXCL
from pyroute2.netlink import NETLINK_NETFILTER
from pyroute2.netlink.exceptions import NetlinkError, IPSetError
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.nfnetlink import NFNL_SUBSYS_IPSET
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_PROTOCOL
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_CREATE
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_DESTROY
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_SWAP
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_LIST
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_ADD
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_DEL
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_FLUSH
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_RENAME
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_TEST
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_TYPE
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_HEADER
from pyroute2.netlink.nfnetlink.ipset import ipset_msg
from pyroute2.netlink.nfnetlink.ipset import IPSET_FLAG_WITH_COUNTERS
from pyroute2.netlink.nfnetlink.ipset import IPSET_FLAG_WITH_COMMENT
from pyroute2.netlink.nfnetlink.ipset import IPSET_FLAG_WITH_FORCEADD
from pyroute2.netlink.nfnetlink.ipset import IPSET_DEFAULT_MAXELEM
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_PROTOCOL
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_FIND_TYPE
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_MAX_SETS
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_BUSY
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_EXIST_SETNAME2
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_TYPE_MISMATCH
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_EXIST
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_INVALID_CIDR
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_INVALID_NETMASK
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_INVALID_FAMILY
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_TIMEOUT
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_REFERENCED
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_IPADDR_IPV4
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_IPADDR_IPV6
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_COUNTER
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_COMMENT
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_INVALID_MARKMASK
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_SKBINFO


def _nlmsg_error(msg):
    return msg['header']['type'] == NLMSG_ERROR


class IPSet(NetlinkSocket):
    '''
    NFNetlink socket (family=NETLINK_NETFILTER).

    Implements API to the ipset functionality.
    '''

    policy = {IPSET_CMD_PROTOCOL: ipset_msg,
              IPSET_CMD_LIST: ipset_msg,
              IPSET_CMD_TYPE: ipset_msg,
              IPSET_CMD_HEADER: ipset_msg}

    def __init__(self, version=6, attr_revision=None, nfgen_family=2):
        super(IPSet, self).__init__(family=NETLINK_NETFILTER)
        policy = dict([(x | (NFNL_SUBSYS_IPSET << 8), y)
                       for (x, y) in self.policy.items()])
        self.register_policy(policy)
        self._proto_version = version
        self._attr_revision = attr_revision
        self._nfgen_family = nfgen_family

    def request(self, msg, msg_type,
                msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
                terminate=None):
        msg['nfgen_family'] = self._nfgen_family
        try:
            return self.nlm_request(msg,
                                    msg_type | (NFNL_SUBSYS_IPSET << 8),
                                    msg_flags, terminate=terminate)
        except NetlinkError as err:
            raise _IPSetError(err.code, cmd=msg_type)

    def headers(self, name):
        '''
        Get headers of the named ipset. It can be used to test if one ipset
        exists, since it returns a no such file or directory.
        '''
        return self._list_or_headers(IPSET_CMD_HEADER, name=name)

    def list(self, *argv, **kwarg):
        '''
        List installed ipsets. If `name` is provided, list
        the named ipset or return an empty list.

        Be warned: netlink does not return an error if given name does not
        exit, you will receive an empty list.
        '''
        if len(argv):
            kwarg['name'] = argv[0]
        return self._list_or_headers(IPSET_CMD_LIST, **kwarg)

    def _list_or_headers(self, cmd, name=None):
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version]]
        if name is not None:
            msg['attrs'].append(['IPSET_ATTR_SETNAME', name])
        return self.request(msg, cmd)

    def destroy(self, name=None):
        '''
        Destroy one or all ipset (when name is None)
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version]]
        if name is not None:
            msg['attrs'].append(['IPSET_ATTR_SETNAME', name])
        return self.request(msg, IPSET_CMD_DESTROY,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK | NLM_F_EXCL,
                            terminate=_nlmsg_error)

    def create(self, name, stype='hash:ip', family=socket.AF_INET,
               exclusive=True, counters=False, comment=False,
               maxelem=IPSET_DEFAULT_MAXELEM, forceadd=False,
               hashsize=None, timeout=None):
        '''
        Create an ipset `name` of type `stype`, by default
        `hash:ip`.

        Common ipset options are supported:

        * exclusive -- if set, raise an error if the ipset exists
        * counters -- enable data/packets counters
        * comment -- enable comments capability
        * maxelem -- max size of the ipset
        * forceadd -- you should refer to the ipset manpage
        * hashsize -- size of the hashtable (if any)
        * timeout -- enable and set a default value for entries (if not None)
        '''
        excl_flag = NLM_F_EXCL if exclusive else 0
        msg = ipset_msg()
        cadt_flags = 0
        if counters:
            cadt_flags |= IPSET_FLAG_WITH_COUNTERS
        if comment:
            cadt_flags |= IPSET_FLAG_WITH_COMMENT
        if forceadd:
            cadt_flags |= IPSET_FLAG_WITH_FORCEADD

        data = {"attrs": [["IPSET_ATTR_CADT_FLAGS", cadt_flags],
                          ["IPSET_ATTR_MAXELEM", maxelem]]}
        if hashsize is not None:
            data['attrs'] += [["IPSET_ATTR_HASHSIZE", hashsize]]
        if timeout is not None:
            data['attrs'] += [["IPSET_ATTR_TIMEOUT", timeout]]

        if self._attr_revision is None:
            # Get the last revision supported by kernel
            revision = self.get_supported_revisions(stype)[1]
        else:
            revision = self._attr_revision
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_SETNAME', name],
                        ['IPSET_ATTR_TYPENAME', stype],
                        ['IPSET_ATTR_FAMILY', family],
                        ['IPSET_ATTR_REVISION', revision],
                        ["IPSET_ATTR_DATA", data]]

        return self.request(msg, IPSET_CMD_CREATE,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK | excl_flag,
                            terminate=_nlmsg_error)

    def _entry_to_data_attrs(self, entry, etype, family):
        attrs = []
        if family is not None:
            if family == socket.AF_INET:
                ip_version = 'IPSET_ATTR_IPADDR_IPV4'
            elif family == socket.AF_INET6:
                ip_version = 'IPSET_ATTR_IPADDR_IPV6'
            elif family == socket.AF_UNSPEC:
                ip_version = None
            else:
                raise TypeError('unknown family')
        for e, t in zip(entry.split(','), etype.split(',')):
            if t in ('ip', 'net'):
                if t == 'net':
                    if '/' in e:
                        e, cidr = e.split('/')
                        attrs += [['IPSET_ATTR_CIDR', int(cidr)]]
                    elif '-' in e:
                        e, to = e.split('-')
                        attrs += [['IPSET_ATTR_IP_TO',
                                   {'attrs': [[ip_version, to]]}]]
                attrs += [['IPSET_ATTR_IP_FROM', {'attrs': [[ip_version, e]]}]]
            elif t == 'iface':
                attrs += [['IPSET_ATTR_IFACE', e]]
            elif t == 'mark':
                attrs += [['IPSET_ATTR_MARK', int(e)]]
            elif t == 'set':
                attrs += [['IPSET_ATTR_NAME', e]]
            elif t == "mac":
                attrs += [['IPSET_ATTR_ETHER', e]]
        return attrs

    def _add_delete_test(self, name, entry, family, cmd, exclusive,
                         comment=None, timeout=None, etype="ip",
                         packets=None, bytes=None):
        excl_flag = NLM_F_EXCL if exclusive else 0

        data_attrs = self._entry_to_data_attrs(entry, etype, family)
        if comment is not None:
            data_attrs += [["IPSET_ATTR_COMMENT", comment],
                           ["IPSET_ATTR_CADT_LINENO", 0]]
        if timeout is not None:
            data_attrs += [["IPSET_ATTR_TIMEOUT", timeout]]
        if bytes is not None:
            data_attrs += [["IPSET_ATTR_BYTES", bytes]]
        if packets is not None:
            data_attrs += [["IPSET_ATTR_PACKETS", packets]]
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_SETNAME', name],
                        ['IPSET_ATTR_DATA', {'attrs': data_attrs}]]

        return self.request(msg, cmd,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK | excl_flag,
                            terminate=_nlmsg_error)

    def add(self, name, entry, family=socket.AF_INET, exclusive=True,
            comment=None, timeout=None, etype="ip", **kwargs):
        '''
        Add a member to the ipset.

        etype is the entry type that you add to the ipset. It's related to
        the ipset type. For example, use "ip" for one hash:ip or bitmap:ip
        ipset.

        When your ipset store a tuple, like "hash:net,iface", you must use a
        comma a separator (etype="net,iface")
        '''
        return self._add_delete_test(name, entry, family, IPSET_CMD_ADD,
                                     exclusive, comment=comment,
                                     timeout=timeout, etype=etype, **kwargs)

    def delete(self, name, entry, family=socket.AF_INET, exclusive=True,
               etype="ip"):
        '''
        Delete a member from the ipset.

        See add method for more information on etype.
        '''
        return self._add_delete_test(name, entry, family, IPSET_CMD_DEL,
                                     exclusive, etype=etype)

    def test(self, name, entry, family=socket.AF_INET, etype="ip"):
        '''
        Test if a member is part of an ipset

        See add method for more information on etype.
        '''
        try:
            self._add_delete_test(name, entry, family, IPSET_CMD_TEST,
                                  False, etype=etype)
            return True
        except IPSetError as e:
            if e.code == IPSET_ERR_EXIST:
                return False
            raise e

    def swap(self, set_a, set_b):
        '''
        Swap two ipsets
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_SETNAME', set_a],
                        ['IPSET_ATTR_TYPENAME', set_b]]
        return self.request(msg, IPSET_CMD_SWAP,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK,
                            terminate=_nlmsg_error)

    def flush(self, name=None):
        '''
        Flush all ipsets. When name is set, flush only this ipset.
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version]]
        if name is not None:
            msg['attrs'].append(['IPSET_ATTR_SETNAME', name])
        return self.request(msg, IPSET_CMD_FLUSH,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK,
                            terminate=_nlmsg_error)

    def rename(self, name_src, name_dst):
        '''
        Rename the ipset.
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_SETNAME', name_src],
                        ['IPSET_ATTR_TYPENAME', name_dst]]
        return self.request(msg, IPSET_CMD_RENAME,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK,
                            terminate=_nlmsg_error)

    def get_supported_revisions(self, stype, family=socket.AF_INET):
        '''
        Return minimum and maximum of revisions supported by the kernel
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_TYPENAME', stype],
                        ['IPSET_ATTR_FAMILY', family]]
        response = self.request(msg, IPSET_CMD_TYPE,
                                msg_flags=NLM_F_REQUEST | NLM_F_ACK,
                                terminate=_nlmsg_error)

        min_revision = response[0].get_attr("IPSET_ATTR_PROTOCOL_MIN")
        max_revision = response[0].get_attr("IPSET_ATTR_REVISION")
        return min_revision, max_revision


class _IPSetError(IPSetError):
    '''
    Proxy class to not import all specifics ipset code in exceptions.py

    Out of the ipset module, a caller should use parent class instead
    '''
    def __init__(self, code, msg=None, cmd=None):
        if code in self.base_map:
            msg = self.base_map[code]
        elif cmd in self.cmd_map:
            error_map = self.cmd_map[cmd]
            if code in error_map:
                msg = error_map[code]
        super(_IPSetError, self).__init__(code, msg)

    base_map = {IPSET_ERR_PROTOCOL: "Kernel error received:"
                                    " ipset protocol error",
                IPSET_ERR_INVALID_CIDR: "The value of the CIDR parameter of"
                                        " the IP address is invalid",
                IPSET_ERR_TIMEOUT: "Timeout cannot be used: set was created"
                                   " without timeout support",
                IPSET_ERR_IPADDR_IPV4: "An IPv4 address is expected, but"
                                       " not received",
                IPSET_ERR_IPADDR_IPV6: "An IPv6 address is expected, but"
                                       " not received",
                IPSET_ERR_COUNTER: "Packet/byte counters cannot be used:"
                                   " set was created without counter support",
                IPSET_ERR_COMMENT: "Comment string is too long!",
                IPSET_ERR_SKBINFO: "Skbinfo mapping cannot be used: "
                                   " set was created without skbinfo support"}

    c_map = {errno.EEXIST: "Set cannot be created: set with the same"
                           " name already exists",
             IPSET_ERR_FIND_TYPE: "Kernel error received: "
                                  "set type not supported",
             IPSET_ERR_MAX_SETS: "Kernel error received: maximal number of"
                                 " sets reached, cannot create more.",
             IPSET_ERR_INVALID_NETMASK: "The value of the netmask parameter"
                                        " is invalid",
             IPSET_ERR_INVALID_MARKMASK: "The value of the markmask parameter"
                                         " is invalid",
             IPSET_ERR_INVALID_FAMILY: "Protocol family not supported by the"
                                       " set type"}

    destroy_map = {IPSET_ERR_BUSY: "Set cannot be destroyed: it is in use"
                                   " by a kernel component"}

    r_map = {IPSET_ERR_EXIST_SETNAME2: "Set cannot be renamed: a set with the"
                                       " new name already exists",
             IPSET_ERR_REFERENCED: "Set cannot be renamed: it is in use by"
                                   " another system"}

    s_map = {IPSET_ERR_EXIST_SETNAME2: "Sets cannot be swapped: the second set"
                                       " does not exist",
             IPSET_ERR_TYPE_MISMATCH: "The sets cannot be swapped: their type"
                                      " does not match"}

    a_map = {IPSET_ERR_EXIST: "Element cannot be added to the set: it's"
                              " already added"}

    del_map = {IPSET_ERR_EXIST: "Element cannot be deleted from the set:"
                                " it's not added"}

    cmd_map = {IPSET_CMD_CREATE: c_map,
               IPSET_CMD_DESTROY: destroy_map,
               IPSET_CMD_RENAME: r_map,
               IPSET_CMD_SWAP: s_map,
               IPSET_CMD_ADD: a_map,
               IPSET_CMD_DEL: del_map}
