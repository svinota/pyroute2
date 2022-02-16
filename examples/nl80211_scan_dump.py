#!/usr/bin/env python3

import sys
import logging

from pyroute2 import IPRoute

from pyroute2.iwutil import IW
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink.nl80211 import nl80211cmd
from pyroute2.netlink.nl80211 import NL80211_NAMES

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger("scandump")
logger.setLevel(level=logging.INFO)

# interface name to dump scan results
ifname = sys.argv[1]

iw = IW()

ip = IPRoute()
ifindex = ip.link_lookup(ifname=ifname)[0]
ip.close()

# CMD_GET_SCAN doesn't require root privileges.
# Can use 'nmcli device wifi' or 'nmcli d w' to trigger a scan which will fill
# the scan results cache for ~30 seconds.
# See also 'iw dev $yourdev scan dump'
msg = nl80211cmd()
msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_SCAN']
msg['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex]]

scan_dump = iw.nlm_request(
    msg, msg_type=iw.prid, msg_flags=NLM_F_REQUEST | NLM_F_DUMP
)
for network in scan_dump:
    for attr in network['attrs']:
        if attr[0] == 'NL80211_ATTR_BSS':
            # handy debugging; see everything we captured
            for bss_attr in attr[1]['attrs']:
                logger.debug("bss attr=%r", bss_attr)

            bss = dict(attr[1]['attrs'])

            # NOTE: the contents of beacon and probe response frames may or
            # may not contain all these fields. Very likely there could be a
            # keyerror in the following code. Needs a bit more bulletproofing.

            # print like 'iw dev $dev scan dump"
            print("BSS {}".format(bss['NL80211_BSS_BSSID']))
            print(
                "\tTSF: {0[VALUE]} ({0[TIME]})".format(bss['NL80211_BSS_TSF'])
            )
            print("\tfreq: {}".format(bss['NL80211_BSS_FREQUENCY']))
            print(
                "\tcapability: {}".format(
                    bss['NL80211_BSS_CAPABILITY']['CAPABILITIES']
                )
            )
            print(
                "\tsignal: {0[VALUE]} {0[UNITS]}".format(
                    bss['NL80211_BSS_SIGNAL_MBM']['SIGNAL_STRENGTH']
                )
            )
            print(
                "\tlast seen: {} ms ago".format(bss['NL80211_BSS_SEEN_MS_AGO'])
            )

            ies = bss['NL80211_BSS_INFORMATION_ELEMENTS']

            # Be VERY careful with the SSID!  Can contain hostile input.
            print("\tSSID: {}".format(ies['SSID'].decode("utf8")))

            # TODO more IE decodes

iw.close()
