import os
import re
import pwd
import platform
import subprocess
from pyroute2 import IPDB
from nose.plugins.skip import SkipTest


def conflict_arch(arch):
    if platform.machine().find(arch) >= 0:
        raise SkipTest('conflict with architecture %s' % (arch))


def require_8021q():
    with IPDB(fork=True) as ip:
        ip.create(kind='dummy', ifname='test_req').commit()
        try:
            ip.create(kind='vlan',
                      ifname='test_vlan',
                      link=ip.interfaces.test_req.index,
                      vlan_id=101).commit()
        except Exception as e:
            if e.code == 95:
                raise SkipTest('required 8021q support')
            else:
                raise
        finally:
            ip.interfaces.test_req.remove()
            ip.interfaces.test_req.commit()


def require_capability(dev):
    # FIXME
    # we should not use IPDB here
    with IPDB(fork=True) as ip:
        try:
            ip.create(kind=dev, ifname='test_req').commit()
        except Exception as e:
            # code 95 'operation not supported'
            if e.code == 95:
                raise SkipTest('required capability <%s>' % (dev))
            else:
                raise
        ip.interfaces.test_req.remove()
        ip.interfaces.test_req.commit()


def require_user(user):
    if bool(os.environ.get('PYROUTE2_TESTS_RO', False)):
        raise SkipTest('read-only tests requested')
    if pwd.getpwuid(os.getuid()).pw_name != user:
        raise SkipTest('required user %s' % (user))


def remove_link(name):
    if os.getuid() != 0:
        return
    with open(os.devnull, 'w') as fnull:
        subprocess.call(['ip', 'link', 'del', 'dev', name],
                        stdout=fnull,
                        stderr=fnull)
    while True:
        links = get_ip_link()
        if name not in links:
            break


def create_link(name, kind):
    if os.getuid() != 0:
        return
    subprocess.call(['ip', 'link', 'add', 'dev', name, 'type', kind])

    for i in range(20):
        links = get_ip_link()
        if name in links:
            return

    raise Exception("interface not created")


def _check_output(*argv):
    # we can not use check_output, as it does not exist in 2.6
    process = subprocess.Popen(argv, stdout=subprocess.PIPE)
    ret = process.communicate()
    return ret[0].decode('ascii').split('\n')


def grep(command, pattern=None):
    out = _check_output(*command.split())
    ret = []
    reg = re.compile(pattern)
    for string in out:
        if reg.search(string):
            ret.append(string)
    return ret


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
            ret.append(fields[1][:-1])
    return ret


def get_ip_default_routes():
    ret = []
    out = _check_output('ip', '-4', 'ro')
    for string in out:
        if 'default' in string:
            ret.append(string)
    return ret


def get_ip_route():
    ret = []
    out = _check_output('ip', '-4', 'ro', 'li', 'ta', '255')
    for string in out:
        if len(string):
            ret.append(string)
    return ret


def get_ip_rules(proto='-4'):
    ret = []
    out = _check_output('ip', proto, 'rule', 'show')
    for string in out:
        if len(string):
            ret.append(string)
    return ret
