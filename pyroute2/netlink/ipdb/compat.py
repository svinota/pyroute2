'''
This module has nothing to do with Netlink in any form. It
provides compatibility functions to run IPDB on ancient
and pre-historical platforms like RHEL 6.5
'''
import os
import time
import platform
import subprocess
from pyroute2.netlink import NetlinkError
_BONDING_MASTERS = '/sys/class/net/bonding_masters'
_BONDING_SLAVES = '/sys/class/net/%s/bonding/slaves'
_BRIDGE_MASTER = '/sys/class/net/%s/brport/bridge/ifindex'
_BONDING_MASTER = '/sys/class/net/%s/master/ifindex'
_ANCIENT_BARRIER = 0.3
_ANCIENT_PLATFORM = (platform.dist()[0] in ('redhat', 'centos') and
                     platform.dist()[1].startswith('6.'))


#
#
#
def bypass(f):
    if _ANCIENT_PLATFORM:
        return f
    else:
        def _bypass(*argv, **kwarg):
            pass
        return _bypass


def replace(r):
    def decorator(f):
        if _ANCIENT_PLATFORM:
            return f
        else:
            return r
    return decorator


@bypass
def fix_del_master(port):
    if 'master' in port:
        port.del_item('master')


@bypass
def fix_add_master(port, master):
    if 'master' not in port:
        port.set_item('master', master['index'])


@bypass
def fix_check_link(nl, index):
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


@bypass
def fix_lookup_master(interface):
    master = get_master(interface['ifname'])
    interface.set_item('master', master)
    return master


@replace(lambda n, l: n.link('delete', index=l['index']))
def fix_del_link(nl, link):
    if link['kind'] == 'bridge':
        del_bridge(link['ifname'])
        time.sleep(_ANCIENT_BARRIER)
    elif link['kind'] == 'bond':
        del_bond(link['ifname'])
        time.sleep(_ANCIENT_BARRIER)
    else:
        nl.link('delete', index=link['index'])


@replace(lambda n, m, p: n.link('set', index=p['index'], master=m['index']))
def fix_add_port(nl, master, port):
    if master['kind'] == 'bridge':
        add_bridge_port(master['ifname'], port['ifname'])
    elif master['kind'] == 'bond':
        add_bond_port(master['ifname'], port['ifname'])
    else:
        nl.link('set', index=port['index'], master=master['index'])


@replace(lambda n, m, p: n.link('set', index=p['index'], master=0))
def fix_del_port(nl, master, port):
    if master['kind'] == 'bridge':
        del_bridge_port(master['ifname'], port['ifname'])
    elif master['kind'] == 'bond':
        del_bond_port(master['ifname'], port['ifname'])
    else:
        nl.link('set', index=port['index'], master=0)


@replace(lambda n, l: n.link('add', **l))
def fix_create_link(nl, link):
    # transparently support ancient platforms
    if link['kind'] == 'bridge':
        create_bridge(link['ifname'])
        time.sleep(_ANCIENT_BARRIER)
    elif link['kind'] == 'bond':
        create_bond(link['ifname'])
        time.sleep(_ANCIENT_BARRIER)
    else:
        # the normal case for any modern kernel
        nl.link('add', **link)


#
# Utility functions to call external programs or set up
# network objects w/o RT netlink, e.g. via sysfs
#
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
        subprocess.check_call(['brctl', 'addbr', name],
                              stdout=fnull,
                              stderr=fnull)


def create_bond(name):
    with open(_BONDING_MASTERS, 'w') as f:
        f.write('+%s' % (name))


def del_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['brctl', 'delbr', name],
                              stdout=fnull,
                              stderr=fnull)


def del_bond(name):
    with open(_BONDING_MASTERS, 'w') as f:
        f.write('-%s' % (name))


def add_bridge_port(master, port):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['brctl', 'addif', master, port],
                              stdout=fnull,
                              stderr=fnull)


def del_bridge_port(master, port):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['brctl', 'delif', master, port],
                              stdout=fnull,
                              stderr=fnull)


def add_bond_port(master, port):
    with open(_BONDING_SLAVES % (master), 'w') as f:
        f.write('+%s' % (port))


def del_bond_port(master, port):
    with open(_BONDING_SLAVES % (master), 'w') as f:
        f.write('-%s' % (port))
