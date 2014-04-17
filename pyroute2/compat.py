'''
This module has nothing to do with Netlink in any form. It
provides compatibility functions to run IPDB on ancient
and pre-historical platforms like RHEL 6.5
'''
import os
import subprocess


def create_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['brctl', 'addbr', name],
                        stdout=fnull,
                        stderr=fnull)


def create_bond(name):
    pass


def del_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['brctl', 'delbr', name],
                        stdout=fnull,
                        stderr=fnull)


def del_bond(name):
    pass


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
    pass


def del_bond_port(master, port):
    pass
