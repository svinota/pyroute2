'''
This module has nothing to do with Netlink in any form. It
provides compatibility functions to run IPDB on ancient
and pre-historical platforms like RHEL 6.5
'''
import os
import subprocess
_BONDING_MASTERS = '/sys/class/net/bonding_masters'
_BONDING_SLAVES = '/sys/class/net/%s/bonding/slaves'
_BRIDGE_MASTER = '/sys/class/net/%s/brport/bridge/ifindex'
_BONDING_MASTER = '/sys/class/net/%s/master/ifindex'


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
