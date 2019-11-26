'''
cake
++++

Usage:

    # Imports
    from pyroute2 import IPRoute


    # Add cake with 2048kbit of bandwidth capacity
    with IPRoute() as ipr:
        # Get interface index
        index = ipr.link_lookup(ifname='lo')
        ipr.tc('add', kind='cake', index=index, bandwidth='2048kbit')

    # Same with 15mbit of bandwidth capacity
    with IPRoute() as ipr:
        # Get interface index
        index = ipr.link_lookup(ifname='lo')
        ipr.tc('add', kind='cake', index=index, bandwidth='15mbit')

    # If you don't known the bandwidth capacity, use autorate
    with IPRoute() as ipr:
        # Get interface index
        index = ipr.link_lookup(ifname='lo')
        ipr.tc('add', kind='cake', index=index, bandwidth='unlimited',
               autorate=True)
'''


from socket import htons
from pyroute2 import protocols
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl import TC_H_ROOT


# Defines from pkt_sched.h
CAKE_FLOW_NONE = 0
CAKE_FLOW_SRC_IP = 1
CAKE_FLOW_DST_IP = 2
CAKE_FLOW_HOSTS = 3
CAKE_FLOW_FLOWS = 4
CAKE_FLOW_DUAL_SRC = 5
CAKE_FLOW_DUAL_DST = 6
CAKE_FLOW_TRIPLE = 7

CAKE_DIFFSERV_DIFFSERV3 = 0
CAKE_DIFFSERV_DIFFSERV4 = 1
CAKE_DIFFSERV_DIFFSERV8 = 2
CAKE_DIFFSERV_BESTEFFORT = 3
CAKE_DIFFSERV_PRECEDENCE = 4

CAKE_ACK_NONE = 0
CAKE_ACK_FILTER = 1
CAKE_ACK_AGGRESSIVE = 2

CAKE_ATM_NONE = 0
CAKE_ATM_ATM = 1
CAKE_ATM_PTM = 2


def fix_msg(msg, kwarg):
    if 'parent' not in kwarg:
        msg['parent'] = TC_H_ROOT


def convert_bandwidth(value):
    types = [('kbit', 1000),
             ('mbit', 1000000),
             ('gbit', 1000000000)
            ]

    if 'unlimited' == value:
        return 0

    try:
        # Value is passed as an int
        x = int(value)
        return x >> 3
    except ValueError:
        value = value.lower()
        for entry in types:
            t, mul = entry
            if len(value.split(t)) == 2:
                x = int(value.split(t)[0]) * mul
                return x >> 3

    raise ValueError('Invalid bandwidth value. Specify either an integer, \
                      "unlimited" or a value with "kbit", "mbit" or \
                      "gbit" appended')


def convert_rtt(value):
    types = [('datacentre', 100),
             ('lan', 1000),
             ('metro', 10000),
             ('regional', 30000),
             ('internet', 100000),
             ('oceanic', 300000),
             ('satellite', 1000000),
             ('interplanetary', 3600000000),
            ]

    try:
        # Value is passed as an int
        x = int(value)
        return x
    except ValueError:
        value = value.lower()
        for entry in types:
            t, rtt = entry
            if value == t:
                return rtt

    raise ValueError('Invalid rtt value. Specify either an integer (us), \
                      or datacentre, lan, metro, regional, internet, oceanic \
                      or interplanetary.')


def convert_atm(value):
    if type(value) is bool:
        if not value:
            return CAKE_ATM_NONE
        else:
            return CAKE_ATM_ATM
    else:
        if value == 'ptm':
            return CAKE_ATM_PTM


def convert_flowmode(value):
    if 'flowblind' == value:
        return CAKE_FLOW_NONE
    elif 'srchost' == value:
        return CAKE_FLOW_SRC_IP
    elif 'dsthost' == value:
        return CAKE_FLOW_DST_IP
    elif 'hosts' == value:
        return CAKE_FLOW_HOSTS
    elif 'flows' == value:
        return CAKE_FLOW_FLOWS
    elif 'dual-srchost' == value:
        return CAKE_FLOW_DUAL_SRC
    elif 'dual-dsthost' == value:
        return CAKE_FLOW_DUAL_DST
    elif 'triple-isolate' == value:
        return CAKE_FLOW_TRIPLE
    else:
        raise ValueError('Invalid flow mode specified! See tc-cake man \
                          page for valid values.')


def convert_diffserv(value):
    if 'diffserv3' == value:
        return CAKE_DIFFSERV_DIFFSERV3
    elif 'diffserv4' == value:
        return CAKE_DIFFSERV_DIFFSERV4
    elif 'diffserv8' == value:
        return CAKE_DIFFSERV_DIFFSERV8
    elif 'besteffort' == value:
        return CAKE_DIFFSERV_BESTEFFORT
    elif 'precedence' == value:
        return CAKE_DIFFSERV_PRECEDENCE
    else:
        raise ValueError('Invalid diffserv mode specified! See tc-cake man \
                          page for valid values.')


def convert_ackfilter(value):
    if type(value) is bool:
        if not value:
            return CAKE_ACK_NONE
        else:
            return CAKE_ACK_FILTER
    else:
        if value == 'aggressive':
            return CAKE_ACK_AGGRESSIVE


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (('ack_filter', 'TCA_CAKE_ACK_FILTER'),
                 ('atm_mode', 'TCA_CAKE_ATM'),
                 ('autorate', 'TCA_CAKE_AUTORATE'),
                 ('bandwidth', 'TCA_CAKE_BASE_RATE64'),
                 ('diffserv_mode', 'TCA_CAKE_DIFFSERV_MODE'),
                 ('flow_mode', 'TCA_CAKE_FLOW_MODE'),
                 ('fwmark', 'TCA_CAKE_FWMARK'),
                 ('memlimit', 'TCA_CAKE_MEMORY'),
                 ('mpu', 'TCA_CAKE_MPU'),
                 ('nat', 'TCA_CAKE_NAT'),
                 ('raw', 'TCA_CAKE_RAW'),
                 ('rtt', 'TCA_CAKE_RTT'),
                 ('wash', 'TCA_CAKE_WASH'),
                 ('overhead', 'TCA_CAKE_OVERHEAD'), #
                 )

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            if k == 'bandwidth':
                r = convert_bandwidth(r)
            elif k == 'rtt':
                r = convert_rtt(r)
            elif k == 'atm':
                r = convert_atm(r)
            elif k == 'flow_mode':
                r = convert_flowmode(r)
            elif k == 'diffserv_mode':
                r = convert_diffserv(r)
            elif k == 'ack_filter':
                r = convert_ackfilter(r)
            ret['attrs'].append([v, r])

    return ret


class options(nla):
    nla_map = (('TCA_CAKE_UNSPEC', 'none'),
               ('TCA_CAKE_PAD', 'uint64'),
               ('TCA_CAKE_BASE_RATE64', 'uint64'),
               ('TCA_CAKE_DIFFSERV_MODE', 'uint32'),
               ('TCA_CAKE_ATM', 'uint32'),
               ('TCA_CAKE_FLOW_MODE', 'uint32'),
               ('TCA_CAKE_OVERHEAD', 'int32'),
               ('TCA_CAKE_RTT', 'uint32'),
               ('TCA_CAKE_TARGET', 'uint32'),
               ('TCA_CAKE_AUTORATE', 'uint32'),
               ('TCA_CAKE_MEMORY', 'uint32'),
               ('TCA_CAKE_NAT', 'uint32'),
               ('TCA_CAKE_RAW', 'uint32'),
               ('TCA_CAKE_WASH', 'uint32'),
               ('TCA_CAKE_MPU', 'uint32'),
               ('TCA_CAKE_INGRESS', 'uint32'),
               ('TCA_CAKE_ACK_FILTER', 'uint32'),
               ('TCA_CAKE_FWMARK', 'uint32'),
               ('TCA_CAKE_FWMARK_STORE', 'uint32'),
               ('TCA_CAKE_SCE', 'uint32'),
               )

    def encode(self):
        # Set default Auto-Rate value
        if not self.get_attr('TCA_CAKE_AUTORATE'):
            self['attrs'].append(['TCA_CAKE_AUTORATE', 0])
        nla.encode(self)
