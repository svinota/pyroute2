from pprint import pprint
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink.nl80211 import nl80211cmd
# from pyroute2.netlink.nl80211 import NL80211_CMD_GET_INTERFACE
from pyroute2.netlink.nl80211 import NL80211_CMD_GET_WIPHY
from pyroute2.netlink.nl80211 import NL80211

nl = NL80211()
nl.bind()
msg = nl80211cmd()
msg['cmd'] = NL80211_CMD_GET_WIPHY
#
# an empty NLA, 4 bytes
#
# 2b == length
# 2b == type
#
msg['attrs'] = [['NL80211_ATTR_SPLIT_WIPHY_DUMP', '']]

# this will send
#
# ## nlmsg header
# \x18\x00\x00\x00 -- length
# \x1b\x00         -- protocol id
# \x01\x03         -- flags
# \xff\x00\x00\x00 -- sequence number
# \x37\x6a\x00\x00 -- pid
#
# ## genlmsg header
# \x01             -- command, NL80211_CMD_GET_WIPHY
# \x00             -- version, ignored
# \x00\x00         -- reserved, ignored
#
# ## NLA chain
# \x04\x00         -- length
# \xae\x00         -- NLA type, NL80211_ATTR_SPLIT_WIPHY_DUMP
#
#
# OBS: iw sends different flags with this request
#
pprint(nl.nlm_request(msg,
                      msg_type=nl.prid,
                      msg_flags=NLM_F_REQUEST | NLM_F_DUMP))
