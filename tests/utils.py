import os
import pwd
import subprocess
from nose.plugins.skip import SkipTest


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


def _check_output(*argv):
    # we can not use check_output, as it does not exist in 2.6
    process = subprocess.Popen(argv, stdout=subprocess.PIPE)
    return process.communicate()[0].split('\n')


def get_ip_addr(interface=None):
    argv = ['ip', '-o', 'ad']
    if interface:
        argv.extend(['li', 'dev', interface])
    out = _check_output(*argv)
    ret = []
    for string in out:
        fields = string.split()
        if len(fields) >= 5 and fields[2][:4] == 'inet':
            ret.append(fields[3])
    return ret


def get_ip_link():
    ret = []
    out = _check_output('ip', '-o', 'li')
    for string in out:
        fields = string.split()
        if len(fields) >= 2:
            ret.append([fields[1][:-1]])
    return ret


def get_ip_route():
    ret = []
    out = _check_output('ip', '-4', 'ro', 'li', 'ta', '255')
    for string in out:
        if len(string):
            ret.append(string)
    return ret
