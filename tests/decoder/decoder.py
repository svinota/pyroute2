#!/usr/bin/python
'''
Usage::

    ./decoder.py [module] [data_file]

Sample::

    ./decoder.py pyroute2.netlink.rtnl.tcmsg.tcmsg ./sample_packet_01.data
    ./decoder.py pyroute2.netlink.nl80211.nl80211cmd ./nl80211.data

Module is a name within rtnl hierarchy. File should be a
binary data in the escaped string format (see samples).
'''
import argparse
import struct
from importlib import import_module
from pprint import pprint

from pyroute2.common import hexdump, load_dump

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument(
    'message_class', help='message class to use for decoding the data'
)
argument_parser.add_argument('data_file', help='data dump file')
argument_parser.add_argument(
    '-f', '--format', default='hex', help='data file format: hex, pcap'
)
argument_parser.add_argument(
    '-m',
    '--match',
    default=0,
    type=int,
    help='match protocol family (only for pcap data)',
)
args = argument_parser.parse_args()

mod = args.message_class
mod = mod.replace('/', '.')
s = mod.split('.')
package = '.'.join(s[:-1])
module = s[-1]
print(package, module)
m = import_module(package)
met = getattr(m, module)
data = None

if args.format == 'hex':
    with open(args.data_file, 'r') as f:
        data = load_dump(f)
elif args.format == 'pcap':
    with open(args.data_file, 'rb') as f:
        data = f.read()

offset = 0
inbox = []
if args.format == 'pcap':
    # read the global header
    pcap_header = struct.unpack('IHHiIII', data[:24])
    offset = 24
while offset < len(data):
    msg = None
    if args.format == 'pcap':
        packet_header = struct.unpack('IIII', data[offset : offset + 16])
        print('pcap packet header', hexdump(data[offset : offset + 16]))
        offset += 16
        length = packet_header[2]
        print('length', length)
        print('link layer header', hexdump(data[offset : offset + 16]))
        ll_header = struct.unpack('HHIIHH', data[offset : offset + 16])
        print('family', ll_header[5])
        if args.match == ll_header[5]:
            msg = met(data[offset + 16 : offset + length])
        offset += length
    else:
        msg = met(data[offset:])
    if msg is not None:
        msg.decode()
        print(hexdump(msg.data))
        pprint(msg)
        print('.' * 40)
    if args.format == 'hex':
        offset += msg['header']['length']
