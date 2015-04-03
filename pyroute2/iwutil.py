'''
IW module
=========

Experimental wireless module -- nl80211 support.

In the very initial state.
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
        '''
        Get all list of phy device
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_WIPHY']
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def _get_phy_name(self, attr):
        return 'phy%i' % int(attr.get_attr('NL80211_ATTR_WIPHY')[:2])

    def _get_frequency(self, attr):
        try:
            return int(attr.get_attr('NL80211_ATTR_WIPHY_FREQ')[:2], 16) + 2304
        except:
            return 0

    def get_interfaces_dict(self):
        '''
        Get interfaces dictionary
        '''
        ret = {}
        for a in self.get_interfaces_dump():
            chan_width = a.get_attr('NL80211_ATTR_CHANNEL_WIDTH')
            freq = self._get_frequency(a) if chan_width is not None else 0
            ret[a.get_attr('NL80211_ATTR_IFNAME')] = [a.get_attr('NL80211_ATTR_IFINDEX'), self._get_phy_name(a), a.get_attr('NL80211_ATTR_MAC'),
                                                      freq, chan_width]

        return ret

    def get_interfaces_dump(self):
        '''
        Get interfaces dump ( use x.get_attr('NL80211_ATTR_WIPHY') )
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_INTERFACE']
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def get_interface_by_phy(self, attr):
        '''
        Get interface by phy name ( use x.get_attr('NL80211_ATTR_WIPHY') )
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_INTERFACE']
        msg['attrs'] = [['NL80211_ATTR_WIPHY', attr]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def get_interface_by_ifindex(self, ifindex):
        '''
        Get interface by ifindex ( use x.get_attr('NL80211_ATTR_IFINDEX')
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_INTERFACE']
        msg['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST)

    def connect(self, ifindex, ssid, bssid=None):
        '''
        Connect to the ap with ssid and bssid
        Warn: Use of put because message does return nothing,
        Use this function with the good right (Root or may be setcap )
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_CONNECT']
        msg['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex],
                        ['NL80211_ATTR_SSID', ssid]]
        if bssid is not None:
            msg['attrs'].append(['NL80211_ATTR_MAC', bssid])

        self.put(msg, msg_type=self.prid, msg_flags=NLM_F_REQUEST)

    def disconnect(self, ifindex):
        '''
        Disconnect the device
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_DISCONNECT']
        msg['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex]]
        self.put(msg, msg_type=self.prid, msg_flags=NLM_F_REQUEST)

    def scan(self, ifindex):
        '''
        Scan wifi
        '''
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_TRIGGER_SCAN']
        msg['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex]]
        self.put(msg, msg_type=self.prid,
                 msg_flags=NLM_F_REQUEST)

        scanResultNotFound = True
        while scanResultNotFound:
            listMsg = self.get()
            for msg in listMsg:
                if msg["event"] == "NL80211_CMD_NEW_SCAN_RESULTS":
                    scanResultNotFound = False
                    break
        msg2 = nl80211cmd()
        msg2['cmd'] = NL80211_NAMES['NL80211_CMD_GET_SCAN']
        msg2['attrs'] = [['NL80211_ATTR_IFINDEX', ifindex]]
        return self.nlm_request(msg2, msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)
