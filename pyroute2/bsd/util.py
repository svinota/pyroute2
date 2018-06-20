'''
Utility to parse ifconfig, netstat etc.

PF_ROUTE may be effectively used only to get notifications. To fetch
info from the system we have to use ioctl or external utilities.

Maybe some day it will be ioctl. For now it's ifconfig and netstat.
'''
import re
import socket
import subprocess


class Route(object):

    def run(self):
        '''
        Run the command and get stdout
        '''
        cmd = ['netstat', '-nr']
        stdout = stderr = ''
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            (stdout, stderr) = process.communicate()
        except Exception:
            process.kill()
        finally:
            process.wait()
        return stdout

    def parse(self, data):

        ret = []
        family = 0
        for line in data.split('\n'):
            if line == 'Internet:':
                family = socket.AF_INET
            elif line == 'Internet6:':
                # do NOT support IPv6 routes yet
                break

            sl = line.split()
            if len(sl) < 4:
                continue
            if sl[0] == 'Destination':
                # create the field map
                fmap = dict([(x[1], x[0]) for x in enumerate(sl)])
                if 'Netif' not in fmap:
                    fmap['Netif'] = fmap['Iface']
                continue

            route = {'family': family,
                     'attrs': []}

            #
            # RTA_DST
            dst = sl[fmap['Destination']]
            if dst != 'default':
                dst = dst.split('/')
                if len(dst) == 2:
                    dst, dst_len = dst
                else:
                    dst = dst[0]
                    if family == socket.AF_INET:
                        dst_len = 32
                    else:
                        dst_len = 128
                dst = dst.split('%')
                if len(dst) == 2:
                    dst, _ = dst
                else:
                    dst = dst[0]

                dst = '%s%s' % (dst, '.0' * (3 - dst.count('.')))
                route['dst_len'] = int(dst_len)
                route['attrs'].append(['RTA_DST', dst])
            #
            # RTA_GATEWAY
            gw = sl[fmap['Gateway']]
            if not gw.startswith('link') and not gw.find(':') >= 0:
                route['attrs'].append(['RTA_GATEWAY', sl[fmap['Gateway']]])
            #
            # RTA_OIF -- do not resolve it here! just save
            route['ifname'] = sl[fmap['Netif']]

            ret.append(route)
        return ret


class ARP(object):

    def run(self):
        '''
        Run the command and get stdout
        '''
        cmd = ['arp', '-an']
        stdout = stderr = ''
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            (stdout, stderr) = process.communicate()
        except Exception:
            process.kill()
        finally:
            process.wait()
        return stdout

    def parse(self, data):

        ret = []
        f_dst = 1
        f_addr = 3
        f_ifname = 5
        for line in data.split('\n'):
            sl = line.split()
            if not sl:
                continue

            if sl[0] == 'Host':
                f_dst = 0
                f_addr = 1
                f_ifname = 2
                continue

            dst = sl[f_dst].strip('(').strip(')')
            addr = sl[f_addr]
            ifname = sl[f_ifname]
            neighbour = {'ifindex': 0,
                         'ifname': ifname,
                         'family': 2,
                         'attrs': [['NDA_DST', dst],
                                   ['NDA_LLADDR', addr]]}
            ret.append(neighbour)
        return ret


class Ifconfig(object):

    match = {'NR': re.compile(r'^\b').match}

    def __init__(self, path=''):
        self.path = path

    def run(self):
        '''
        Run the command and get stdout
        '''
        cmd = ['ifconfig', ]
        stdout = stderr = ''
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            (stdout, stderr) = process.communicate()
        except Exception:
            process.kill()
        finally:
            process.wait()
        return stdout

    def parse_line(self, line):
        '''
        Dumb line parser:

        "key1 value1 key2 value2 something"
          -> {"key1": "value1", "key2": "value2"}
        '''
        ret = {}
        cursor = 0
        while cursor < (len(line) - 1):
            ret[line[cursor]] = line[cursor + 1]
            cursor += 2
        return ret

    def parse(self, data):
        '''
        Parse ifconfig output into netlink-compatible dicts::

            from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
            from pyroute2.bsd.util import Ifconfig

            def links()
                ifc = Ifconfig()
                data = ifc.run()
                for name, spec in ifc.parse(data)["links"].items():
                    yield ifinfmsg().load(spec)
        '''
        current = None
        ret = {'links': {},
               'addrs': {}}
        idx = 0
        for line in data.split('\n'):
            sl = line.split()
            pl = self.parse_line(sl)

            # first line -- ifname, flags, mtu
            if self.match['NR'](line):
                current = sl[0][:-1]
                idx += 1
                ret['links'][current] = link = {'index': idx,
                                                'attrs': []}
                ret['addrs'][current] = addrs = []
                link['attrs'].append(['IFLA_IFNAME', current])

                # extract MTU
                if 'mtu' in pl:
                    link['attrs'].append(['IFLA_MTU', int(pl['mtu'])])

            elif 'ether' in pl:
                link['attrs'].append(['IFLA_ADDRESS', pl['ether']])

            elif 'inet' in pl:
                addr = {'index': idx,
                        'family': socket.AF_INET,
                        'prefixlen': bin(int(pl['netmask'], 16)).count('1'),
                        'attrs': [['IFA_ADDRESS', pl['inet']]]}
                if 'broadcast' in pl:
                    addr['attrs'].append(['IFA_BROADCAST', pl['broadcast']])
                addrs.append(addr)
            elif 'inet6' in pl:
                addr = {'index': idx,
                        'family': socket.AF_INET6,
                        'prefixlen': int(pl['prefixlen']),
                        'attrs': [['IFA_ADDRESS', pl['inet6'].split('%')[0]]]}
                if 'scopeid' in pl:
                    addr['scope'] = int(pl['scopeid'], 16)
                addrs.append(addr)
        return ret
