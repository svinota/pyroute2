from pprint import pprint
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink.nl80211 import nl80211cmd
from pyroute2.netlink.nl80211 import NL80211_CMD_GET_INTERFACE
from pyroute2.netlink.nl80211 import NL80211_CMD_GET_WIPHY
from pyroute2.netlink.nl80211 import NL80211

nl = NL80211()
nl.bind()
msg = nl80211cmd()
msg['cmd'] = NL80211_CMD_GET_INTERFACE
pprint(nl.nlm_request(msg,
                      msg_type=nl.prid,
                      msg_flags=NLM_F_REQUEST | NLM_F_DUMP))
