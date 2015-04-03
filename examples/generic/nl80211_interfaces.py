#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# fcukall.py
from pyroute2.iwutil import IW
from pprint import pprint

iw = IW()
# pprint(iw.get_interface_dict())
# exit()
for q in iw.get_interfaces_dump():
    # pprint(dict(q['attrs']))
    phyname = 'phy%i' % int(q.get_attr('NL80211_ATTR_WIPHY')[:2])
    print('%i\t%s\t%s\t%s' % (q.get_attr('NL80211_ATTR_IFINDEX'), phyname,
                              q.get_attr('NL80211_ATTR_IFNAME'), q.get_attr('NL80211_ATTR_MAC')))
