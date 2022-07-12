import errno
import os
import platform
import pwd
import re
import stat
import subprocess
import sys
import uuid
from socket import AF_INET, AF_INET6

import netaddr
import pytest

from pyroute2 import config
from pyroute2.iproute.linux import IPRoute

try:
    import httplib
except ImportError:
    import http.client as httplib

dtcd_uuid = str(uuid.uuid4())
# check the dtcd
try:
    cx = httplib.HTTPConnection('localhost:7623')
    cx.request('GET', '/v1/network/')
    cx.getresponse()
    has_dtcd = True
except:
    has_dtcd = False

supernet = {
    AF_INET: netaddr.IPNetwork('172.16.0.0/12'),
    AF_INET6: netaddr.IPNetwork('fdb3:84e5:4ff4::/48'),
}
network_pool = {
    AF_INET: list(supernet[AF_INET].subnet(24)),
    AF_INET6: list(supernet[AF_INET6].subnet(64)),
}
allocations = {}
family_url = {AF_INET: 'ipv4', AF_INET6: 'ipv6'}


def allocate_network(family=AF_INET):
    global dtcd_uuid
    global network_pool
    global allocations

    network = None

    try:
        cx = httplib.HTTPConnection('localhost:7623')
        cx.request(
            'POST', '/v1/network/%s/' % family_url[family], body=dtcd_uuid
        )
        resp = cx.getresponse()
        if resp.status == 200:
            network = netaddr.IPNetwork(resp.read().decode('utf-8'))
        cx.close()
    except Exception:
        pass

    if network is None:
        network = network_pool[family].pop()
        allocations[network] = True

    return network


def free_network(network, family=AF_INET):
    global network_pool
    global allocations

    if network in allocations:
        allocations.pop(network)
        network_pool[family].append(network)
    else:
        cx = httplib.HTTPConnection('localhost:7623')
        cx.request(
            'DELETE', '/v1/network/%s/' % family_url[family], body=str(network)
        )
        cx.getresponse()
        cx.close()


def conflict_arch(arch):
    if platform.machine().find(arch) >= 0:
        pytest.skip('conflict with architecture %s' % (arch))


def kernel_version_ge(major, minor):
    # True if running kernel is >= X.Y
    if config.kernel[0] > major:
        return True
    if config.kernel[0] < major:
        return False
    if minor and config.kernel[1] < minor:
        return False
    return True


def require_kernel(major, minor=None):
    if not kernel_version_ge(major, minor):
        pytest.skip('incompatible kernel version')


def require_python(target):
    if sys.version_info[0] != target:
        pytest.skip('test requires Python %i' % target)


def require_8021q():
    try:
        os.stat('/proc/net/vlan/config')
    except OSError as e:
        # errno 2 'No such file or directory'
        if e.errno == 2:
            pytest.skip('missing 8021q support, or module is not loaded')
        raise


def require_bridge():
    with IPRoute() as ip:
        try:
            ip.link('add', ifname='test_req', kind='bridge')
        except Exception:
            pytest.skip('can not create <bridge>')
        idx = ip.link_lookup(ifname='test_req')
        if not idx:
            pytest.skip('can not create <bridge>')
        ip.link('del', index=idx)


def require_bond():
    with IPRoute() as ip:
        try:
            ip.link('add', ifname='test_req', kind='bond')
        except Exception:
            pytest.skip('can not create <bond>')
        idx = ip.link_lookup(ifname='test_req')
        if not idx:
            pytest.skip('can not create <bond>')
        ip.link('del', index=idx)


def require_user(user):
    if bool(os.environ.get('PYROUTE2_TESTS_RO', False)):
        pytest.skip('read-only tests requested')
    if pwd.getpwuid(os.getuid()).pw_name != user:
        pytest.skip('required user %s' % (user))


def require_executable(name):
    try:
        with open(os.devnull, 'w') as fnull:
            subprocess.check_call(['which', name], stdout=fnull, stderr=fnull)
    except Exception:
        pytest.skip('required %s not found' % (name))


def remove_link(name):
    if os.getuid() != 0:
        return
    with open(os.devnull, 'w') as fnull:
        subprocess.call(
            ['ip', 'link', 'del', 'dev', name], stdout=fnull, stderr=fnull
        )
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
    return ret[0].decode('utf-8').split('\n')


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


def get_ip_brd(interface=None):
    argv = ['ip', '-o', 'ad']
    if interface:
        argv.extend(['li', 'dev', interface])
    out = _check_output(*argv)
    ret = []
    for string in out:
        fields = string.split()
        if len(fields) >= 5 and fields[4] == 'brd':
            ret.append(fields[5])
    return ret


def get_ip_link():
    ret = []
    out = _check_output('ip', '-o', 'li')
    for string in out:
        fields = string.split()
        if len(fields) >= 2:
            ret.append(fields[1][:-1].split('@')[0])
    return ret


def get_ip_default_routes():
    ret = []
    out = _check_output('ip', '-4', 'ro')
    for string in out:
        if 'default' in string:
            ret.append(string)
    return ret


def get_ip_rules(proto='-4'):
    ret = []
    out = _check_output('ip', proto, 'rule', 'show')
    for string in out:
        if len(string):
            ret.append(string)
    return ret


def count_socket_fds():
    pid_fd = '/proc/%s/fd' % os.getpid()
    sockets = 0
    for fd in os.listdir(pid_fd):
        try:
            if stat.S_ISSOCK(os.stat(os.path.join(pid_fd, fd)).st_mode):
                sockets += 1
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    return sockets
