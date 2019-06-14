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
logger.setLevel(level=logging.DEBUG)
# logger.setLevel(level=logging.INFO)

logging.getLogger("pyroute2").setLevel(level=logging.DEBUG)


def print_ht_capabilities(ht_capa):
    if not ht_capa:
        return

    print("\tHT capabilities:")
    # TODO get actual value
    print("\t\tcapabilities: %#06x" % 0)

    # Capability Information field
    _, ht_cap_info = ht_capa[0]
    for i, field in enumerate(ht_cap_info):
        if field is None:
            # ignore reserved bits
            continue

        # need special purpose print for some fields
        s = None
        if i == 1:
            s = "%s" % ht_capa.channel_width_str(field.value)
        elif i == 2:
            # powersave:
            s = "%s" % ht_capa.sm_power_save_str(field.value)
        elif i == 8:
            s = "%s" % ht_capa.rx_stbc_str(field.value)
        elif i == 11:
            s = "%s: %d" % (field[0], ht_capa.max_amsdu_len(field.value))
        elif field.value:
            # assume it's a boolen bit field that's only printed if true
            s = "%s" % field.name
        if s:
            print("\t\t\t%s" % s)

    # TODO AMPDU print
    _, ampdu = ht_capa[1]

    # TODO print MCS indices
    _, mcs = ht_capa[2]


def print_ht_operation(ht_capa):
    if not ht_capa:
        return

    print("\tHT operation: TODO")


def print_vht_capabilities(vht_capa):
    if not vht_capa:
        return

    # TODO need a value for the 32-bit cap info field
    print("\tVHT capabilities:\n\t\tVHT Capabilities ({0:#010x}):".format(0))

    _, vht_cap_info = vht_capa[0]
    for i, field in enumerate(vht_cap_info):
        if field is None:
            continue

        s = None
        if i == 0:
            s = "%s: %d" % (field[0], vht_capa.max_mpdu_len(field[1]))
        if i == 2:
            s = "%s: %s" % (
                field[0],
                vht_capa.supported_chan_width_str(field[1]))
        elif field[1]:
            s = field[0]
        if s:
            print("\t\t\t%s" % s)


def print_bss(bss):
    # NOTE: the contents of beacon and probe response frames may or may not
    # contain all these fields.  Very likely there could be a keyerror in the
    # following code. Needs a bit more bulletproofing.

    # print like 'iw dev $dev scan dump"
    print("BSS {}".format(bss['NL80211_BSS_BSSID']))
    print("\tTSF: {0[VALUE]} ({0[TIME]})".format(bss['NL80211_BSS_TSF']))
    print("\tfreq: {}".format(bss['NL80211_BSS_FREQUENCY']))
    print("\tcapability: {}".format(
        bss['NL80211_BSS_CAPABILITY']['CAPABILITIES']))
    print("\tsignal: {0[VALUE]} {0[UNITS]}".format(
        bss['NL80211_BSS_SIGNAL_MBM']['SIGNAL_STRENGTH']))
    print("\tlast seen: {} ms ago".format(bss['NL80211_BSS_SEEN_MS_AGO']))

    # each IE should be an instance of nl80211.IE
    ies = bss['NL80211_BSS_INFORMATION_ELEMENTS']

    # Be VERY careful with the SSID!  Can contain hostile input.
    # For example, this print is vulnerable to an SSID with terminal escape
    # chars. https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    print("\tSSID: {}".format(ies['SSID'].decode("utf8")))

    print("\tSupported rates: {}".format(ies["SUPPORTED_RATES"]))

    print("\tDS Parameter set: TODO")
    print("\tCountry: TODO")

    try:
        print("\tExtended supported rates: {}".format(ies['EXTENDED_RATES']))
    except KeyError:
        pass

    try:
        print_ht_capabilities(ies["HT_CAPABILITIES"])
    except KeyError:
        pass

    try:
        print_ht_operation(ies["HT_OPERATION"])
    except KeyError:
        pass

    try:
        if ies['EXTENDED_CAPABILITIES']:
            s = "\n\t\t* ".join(ies['EXTENDED_CAPABILITIES'])
            print("\tExtended capabilities:\n\t\t* " + s)
    except KeyError:
        pass

    try:
        print_vht_capabilities(ies['VHT_CAPABILITIES'])
    except KeyError:
        pass

    # TODO more IE decodes


def main(ifname):
    iw = IW()

    ip = IPRoute()
    ifindex = ip.link_lookup(ifname=ifname)[0]
    ip.close()

    # CMD_GET_SCAN doesn't require root privileges.
    # Can use 'nmcli device wifi' or 'nmcli d w' to trigger a scan which will
    # fill the scan results cache for ~30 seconds.
    # See also 'iw dev $yourdev scan dump'
    msg = nl80211cmd()
    msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_SCAN']
    msg['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex]]

    scan_dump = iw.nlm_request(msg, msg_type=iw.prid,
                               msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    for network in scan_dump:
        for attr in network['attrs']:
            logger.debug("attr={}".format(attr))

            if attr[0] == 'NL80211_ATTR_BSS':
                # handy debugging; see everything we captured
                for bss_attr in attr[1]['attrs']:
                    logger.debug("bss attr=%r", bss_attr)

                bss = dict(attr[1]['attrs'])
                print_bss(bss)

    iw.close()


if __name__ == '__main__':
    # interface name to dump scan results
    ifname = sys.argv[1]
    main(ifname)
