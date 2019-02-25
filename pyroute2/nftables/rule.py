
from pyroute2.nftables.parser.parser import nfta_nla_parser, conv_map_tuple
from pyroute2.nftables.parser.expr import get_expression_from_netlink, get_expression_from_dict


class NFTRule(nfta_nla_parser):

    conv_maps = (
        conv_map_tuple('table', 'NFTA_RULE_TABLE', 'table', 'raw'),
        conv_map_tuple('chain', 'NFTA_RULE_CHAIN', 'chain', 'raw'),
        conv_map_tuple('handle', 'NFTA_RULE_HANDLE', 'handle', 'raw'),
        conv_map_tuple('expressions', 'NFTA_RULE_EXPRESSIONS', 'expr', 'expressions_list'),
        #conv_map_tuple('compat', 'NFTA_RULE_COMPAT', 'compat', 'ascii'),
        conv_map_tuple('position', 'NFTA_RULE_POSITION', 'position', 'raw'),
        conv_map_tuple('userdata', 'NFTA_RULE_USERDATA', 'userdata', 'user_data'),
        #conv_map_tuple('rule_id', 'NFTA_RULE_ID', 'rule_id', 'NLA_U32'),
        #conv_map_tuple('position_id', 'NFTA_RULE_POSITION_ID', 'position_id', 'NLA_U32'),
    )

    def __init__(self, family='inet', **kwargs):
        self.family = family
        super(NFTRule, self).__init__(**kwargs)


    class cparser_user_data(object):
        def __init__(self, udata_type, value):
            self.type = udata_type
            self.value = value

        @classmethod
        def from_netlink(cls, userdata):
            userdata = [int(d, 16) for d in userdata.split(':')]
            udata_type = userdata[0]
            udata_len = userdata[1]
            udata_value = ''.join([chr(d) for d in userdata[2:udata_len+2]])
            if udata_type == 0: # 0 == COMMENT
                return cls('comment', udata_value)
            raise NotImplementedError("userdata type: {0}".format(udata_type))

        @staticmethod
        def to_netlink(udata):
            if udata.type == 'comment':
                userdata = '00:'
            else:
                raise NotImplementedError("userdata type: {0}".format(udata.type))
            userdata += "%0.2X:" % len(udata.value)
            userdata += ':'.join(["%0.2X" % ord(d) for d in udata.value])
            return userdata

        @staticmethod
        def to_dict(udata):
            # Currently nft command to not export userdata to dict
            return None
            if udata.type == "comment":
                return {"type": "comment", "value": udata.value}
            raise NotImplementedError("userdata type: {0}".format(udata.type))

        @classmethod
        def from_dict(cls, d):
            # See to_dict() method
            return None

    class cparser_expressions_list(object):

        @staticmethod
        def from_netlink(expressions):
            return [get_expression_from_netlink(e) for e in expressions]

        @staticmethod
        def to_netlink(expressions):
            return [e.to_netlink() for e in expressions]

        @staticmethod
        def from_dict(expressions):
            return [get_expression_from_dict(e) for e in expressions]

        @staticmethod
        def to_dict(expressions):
            print(expressions)
            return [e.to_dict() for e in expressions]
