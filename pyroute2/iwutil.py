'''
IW module
=========

Experimental module
'''
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink.nl80211 import NL80211
from pyroute2.netlink.nl80211 import nl80211cmd
from pyroute2.netlink.nl80211 import NL80211_NAMES


class IW(NL80211):

    def __init__(self, *argv, **kwarg):
        # get specific groups kwarg
        if 'groups' in kwarg:
            groups = kwarg['groups']
            del kwarg['groups']
        else:
            groups = None

        # get specific async kwarg
        if 'async' in kwarg:
            async = kwarg['async']
            del kwarg['async']
        else:
            async = False

        # align groups with async
        if groups is None:
            groups = ~0 if async else 0

        # continue with init
        super(IW, self).__init__(*argv, **kwarg)

        # do automatic bind
        # FIXME: unfortunately we can not omit it here
        self.bind(groups, async)

    def list_wiphy(self):
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_WIPHY']
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def get_interface_by_phy(self, attr):
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_INTERFACE']
        msg['attrs'] = [['NL80211_ATTR_WIPHY', attr]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def info_interface_by_ifindex(self, index):
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_INTERFACE']
        msg['attrs'] = [['NL80211_ATTR_IFINDEX', index]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST)
