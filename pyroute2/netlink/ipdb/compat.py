'''
This module has nothing to do with Netlink in any form. It
provides compatibility functions to run IPDB on ancient
and pre-historical platforms like RHEL 6.5
'''
import os
import platform
import subprocess
from pyroute2.netlink import NetlinkError
_BONDING_MASTERS = '/sys/class/net/bonding_masters'
_BONDING_SLAVES = '/sys/class/net/%s/bonding/slaves'
_BRIDGE_MASTER = '/sys/class/net/%s/brport/bridge/ifindex'
_BONDING_MASTER = '/sys/class/net/%s/master/ifindex'
_ANCIENT_PLATFORM = (platform.dist()[0] in ('redhat', 'centos') and
                     platform.dist()[1].startswith('6.'))


def fix_del_master(port):
    if _ANCIENT_PLATFORM and 'master' in port:
        port.del_item('master')


def fix_add_master(port, master):
    if _ANCIENT_PLATFORM and 'master' not in port:
        port.set_item('master', master['index'])


def fix_check_link(nl, index):
    if _ANCIENT_PLATFORM:
        # swith mirror off
        nl.mirror(False)
        # check, if the link really exits --
        # on some old kernels you can receive
        # broadcast RTM_NEWLINK after the link
        # was deleted
        try:
            nl.get_links(index)
        except NetlinkError as e:
            if e.code == 19:  # No such device
                # just drop this message then
                return True
        finally:
            nl.mirror(True)


def fix_lookup_master(interface):
    if _ANCIENT_PLATFORM:
        master = get_master(interface['ifname'])
        interface.set_item('master', master)
        return master


def fix_del_link(nl, link):
    if _ANCIENT_PLATFORM and link['kind'] == 'bridge':
        del_bridge(link['ifname'])
    elif _ANCIENT_PLATFORM and link['kind'] == 'bond':
        del_bond(link['ifname'])
    else:
        nl.link('delete', index=link['index'])


def fix_add_port(nl, master, port):
    if _ANCIENT_PLATFORM and master['kind'] == 'bridge':
        add_bridge_port(master['ifname'], port['ifname'])
    elif _ANCIENT_PLATFORM and master['kind'] == 'bond':
        add_bond_port(master['ifname'], port['ifname'])
    else:
        nl.link('set', index=port['index'], master=master['index'])


def fix_del_port(nl, master, port):
    if _ANCIENT_PLATFORM and master['kind'] == 'bridge':
        del_bridge_port(master['ifname'], port['ifname'])
    elif _ANCIENT_PLATFORM and master['kind'] == 'bond':
        del_bond_port(master['ifname'], port['ifname'])
    else:
        nl.link('set', index=port['index'], master=0)


def fix_create_link(nl, link):
    # transparently support ancient platforms
    if _ANCIENT_PLATFORM and link['kind'] == 'bridge':
        create_bridge(link['ifname'])
    elif _ANCIENT_PLATFORM and link['kind'] == 'bond':
        create_bond(link['ifname'])
    else:
        # the normal case for any modern kernel
        nl.link('add', **link)


def get_master(name):
    f = None

    for i in (_BRIDGE_MASTER, _BONDING_MASTER):
        try:
            f = open(i % (name))
            break
        except IOError:
            pass

    if f is not None:
        master = int(f.read())
        f.close()
        return master


def create_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['brctl', 'addbr', name],
                        stdout=fnull,
                        stderr=fnull)


def create_bond(name):
    with open(_BONDING_MASTERS, 'w') as f:
        f.write('+%s' % (name))


def del_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['brctl', 'delbr', name],
                        stdout=fnull,
                        stderr=fnull)


def del_bond(name):
    with open(_BONDING_MASTERS, 'w') as f:
        f.write('-%s' % (name))


def add_bridge_port(master, port):
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['brctl', 'addif', master, port],
                        stdout=fnull,
                        stderr=fnull)


def del_bridge_port(master, port):
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['brctl', 'delif', master, port],
                        stdout=fnull,
                        stderr=fnull)


def add_bond_port(master, port):
    with open(_BONDING_SLAVES % (master), 'w') as f:
        f.write('+%s' % (port))


def del_bond_port(master, port):
    with open(_BONDING_SLAVES % (master), 'w') as f:
        f.write('-%s' % (port))
