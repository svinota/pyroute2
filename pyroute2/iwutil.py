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
        super(IW, self).__init__(*argv, **kwarg)
        self.bind(~0,True)

	
	self.register_callback(self.getMessage.__func__)

    def getMessage(self,msg):
	print(msg)


    #obj[0].get_attr('NL80211_ATTR_WIPHY_NAME')

    def listWiPhy(self):
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_WIPHY']
        #msg['attrs'] = [['NL80211_ATTR_IFINDEX', index]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags= NLM_F_REQUEST | NLM_F_DUMP)


    def getInterfaceByPhy(self,attr):
	#NL80211_CMD_GET_INTERFACE
	msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_INTERFACE']
        msg['attrs'] = [['NL80211_ATTR_WIPHY', attr]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def infoInterfaceByIfIndex(self,index):
        msg = nl80211cmd()
        msg['cmd'] = NL80211_NAMES['NL80211_CMD_GET_WIPHY']
        msg['attrs'] = [['NL80211_ATTR_IFINDEX', index]]
        return self.nlm_request(msg,
                                msg_type=self.prid,
                                msg_flags=NLM_F_REQUEST | NLM_F_DUMP)



	
