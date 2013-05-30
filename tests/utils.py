import os
import pwd
import subprocess
from unittest import SkipTest


def require_user(user):
    if pwd.getpwuid(os.getuid()).pw_name != user:
        raise SkipTest('required user %s' % (user))


def remove_link(name):
    if os.getuid() != 0:
        return
    subprocess.call(['ip', 'link', 'del', 'dev', name])


def create_link(name, kind):
    if os.getuid() != 0:
        return
    subprocess.call(['ip', 'link', 'add', 'dev', name, 'type', kind])


def setup_dummy():
    if os.getuid() != 0:
        return
    create_link('dummyX', 'dummy')
    for i in range(1, 20):
        ip = '172.16.13.%i/24' % (i)
        subprocess.call(['ip', 'addr', 'add', 'dev', 'dummyX', ip])


def remove_dummy():
    remove_link('dummyX')


def get_ip_addr(interface=None):
    argv = ['ip', '-o', 'ad']
    if interface:
        argv.extend(['li', 'dev', interface])
    out = subprocess.check_output(argv).split('\n')
    ret = []
    for string in out:
        fields = string.split()
        if len(fields) >= 5 and fields[2][:4] == 'inet':
            ret.append(fields[3])
    return ret


def get_ip_link():
    ret = []
    out = subprocess.check_output(['ip', '-o', 'li']).split('\n')
    for string in out:
        fields = string.split()
        if len(fields) >= 2:
            ret.append([fields[1][:-1]])
    return ret


def get_ip_route():
    ret = []
    out = subprocess.check_output(['ip',
                                   '-4',
                                   'ro',
                                   'li',
                                   'ta',
                                   '255']).split('\n')
    for string in out:
        if len(string):
            ret.append(string)
    return ret
