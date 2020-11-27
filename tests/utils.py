import os
import re
import pwd
import stat
import sys
import uuid
import errno
import platform
import subprocess
import netaddr
import ctypes
import ctypes.util
from pyroute2 import NetlinkError
from pyroute2 import IPRoute
from nose.plugins.skip import SkipTest
from nose.tools import make_decorator
from distutils.version import LooseVersion
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

supernet = {'ipv4': netaddr.IPNetwork('172.16.0.0/12'),
            'ipv6': netaddr.IPNetwork('fdb3:84e5:4ff4::/48')}
network_pool = {'ipv4': list(supernet['ipv4'].subnet(24)),
                'ipv6': list(supernet['ipv6'].subnet(64))}
allocations = {}


def allocate_network(ipv='ipv4'):
    global dtcd_uuid
    global network_pool
    global allocations

    network = None

    try:
        cx = httplib.HTTPConnection('localhost:7623')
        cx.request('POST', '/v1/network/%s/' % ipv, body=dtcd_uuid)
        resp = cx.getresponse()
        if resp.status == 200:
            network = netaddr.IPNetwork(resp.read().decode('utf-8'))
        cx.close()
    except Exception:
        pass

    if network is None:
        network = network_pool[ipv].pop()
        allocations[network] = True

    return network


def free_network(network, ipv='ipv4'):
    global network_pool
    global allocations

    if network in allocations:
        allocations.pop(network)
        network_pool[ipv].append(network)
    else:
        cx = httplib.HTTPConnection('localhost:7623')
        cx.request('DELETE', '/v1/network/%s/' % ipv, body=str(network))
        cx.getresponse()
        cx.close()


def skip_if_not_supported(f):
    def test_wrapper(self, *argv, **kwarg):
        try:
            return f(self, *argv, **kwarg)
        except NetlinkError as e:
            if e.code == errno.EOPNOTSUPP:
                raise SkipTest('feature not supported by platform')
            raise
        except RuntimeError as e:
            if hasattr(e, 'client_error'):
                if ((isinstance(e.client_error, NetlinkError) and
                     e.client_error.code == errno.EOPNOTSUPP) or
                    (isinstance(e.server_error, NetlinkError) and
                     e.server_error.code == errno.EOPNOTSUPP)):
                    raise SkipTest('feature not supported by platform')
            elif not getattr(e, 'feature_supported', True):
                raise SkipTest(e.args[0])
            raise
        except Exception:
            raise
    return make_decorator(f)(test_wrapper)


def conflict_arch(arch):
    if platform.machine().find(arch) >= 0:
        raise SkipTest('conflict with architecture %s' % (arch))


def kernel_version_ge(major, minor):
    # True if running kernel is >= X.Y
    version = LooseVersion(os.uname()[2]).version
    if version[0] > major:
        return True
    if version[0] < major:
        return False
    if minor and version[1] < minor:
        return False
    return True


def require_kernel(major, minor=None):
    if not kernel_version_ge(major, minor):
        raise SkipTest('incompatible kernel version')


def require_python(target):
    if sys.version_info[0] != target:
        raise SkipTest('test requires Python %i' % target)


def require_8021q():
    try:
        os.stat('/proc/net/vlan/config')
    except OSError as e:
        # errno 2 'No such file or directory'
        if e.errno == 2:
            raise SkipTest('missing 8021q support, or module is not loaded')
        raise


def require_bridge():
    with IPRoute() as ip:
        try:
            ip.link('add', ifname='test_req', kind='bridge')
        except Exception:
            raise SkipTest('can not create <bridge>')
        idx = ip.link_lookup(ifname='test_req')
        if not idx:
            raise SkipTest('can not create <bridge>')
        ip.link('del', index=idx)


def require_bond():
    with IPRoute() as ip:
        try:
            ip.link('add', ifname='test_req', kind='bond')
        except Exception:
            raise SkipTest('can not create <bond>')
        idx = ip.link_lookup(ifname='test_req')
        if not idx:
            raise SkipTest('can not create <bond>')
        ip.link('del', index=idx)


def require_user(user):
    if bool(os.environ.get('PYROUTE2_TESTS_RO', False)):
        raise SkipTest('read-only tests requested')
    if pwd.getpwuid(os.getuid()).pw_name != user:
        raise SkipTest('required user %s' % (user))


def require_executable(name):
    try:
        with open(os.devnull, 'w') as fnull:
            subprocess.check_call(['which', name],
                                  stdout=fnull,
                                  stderr=fnull)
    except Exception:
        raise SkipTest('required %s not found' % (name))


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


def get_bpf_syscall_num():
    # determine bpf syscall number
    prog = """
#include <asm/unistd.h>
#define XSTR(x) STR(x)
#define STR(x) #x
#pragma message "__NR_bpf=" XSTR(__NR_bpf)
"""
    cmd = ['gcc', '-x', 'c', '-c', '-', '-o', '/dev/null']
    gcc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    out = gcc.communicate(input=prog.encode('ascii'))[1]
    m = re.search('__NR_bpf=([0-9]+)', str(out))
    if not m:
        raise SkipTest('bpf syscall not available')
    return int(m.group(1))


def get_simple_bpf_program(prog_type):
    NR_bpf = get_bpf_syscall_num()

    class BPFAttr(ctypes.Structure):
        _fields_ = [('prog_type', ctypes.c_uint),
                    ('insn_cnt', ctypes.c_uint),
                    ('insns', ctypes.POINTER(ctypes.c_ulonglong)),
                    ('license', ctypes.c_char_p),
                    ('log_level', ctypes.c_uint),
                    ('log_size', ctypes.c_uint),
                    ('log_buf', ctypes.c_char_p),
                    ('kern_version', ctypes.c_uint)]

    BPF_PROG_TYPE_SCHED_CLS = 3
    BPF_PROG_TYPE_SCHED_ACT = 4
    BPF_PROG_LOAD = 5
    insns = (ctypes.c_ulonglong * 2)()
    # equivalent to: int my_func(void *) { return 1; }
    insns[0] = 0x00000001000000b7
    insns[1] = 0x0000000000000095
    license = ctypes.c_char_p(b'GPL')
    if prog_type.lower() == "sched_cls":
        attr = BPFAttr(BPF_PROG_TYPE_SCHED_CLS, len(insns),
                       insns, license, 0, 0, None, 0)
    elif prog_type.lower() == "sched_act":
        attr = BPFAttr(BPF_PROG_TYPE_SCHED_ACT, len(insns),
                       insns, license, 0, 0, None, 0)
    libc = ctypes.CDLL(ctypes.util.find_library('c'))
    libc.syscall.argtypes = [ctypes.c_long, ctypes.c_int,
                             ctypes.POINTER(type(attr)), ctypes.c_uint]
    libc.syscall.restype = ctypes.c_int
    fd = libc.syscall(NR_bpf, BPF_PROG_LOAD, attr, ctypes.sizeof(attr))
    return fd


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
