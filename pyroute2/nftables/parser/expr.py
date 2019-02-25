"""
nf_tables expression netlink attributes

See EXPRESSIONS in nft(8).
"""

NFTA_EXPR_NAME_MAP = {
}


def get_expression_from_netlink(ndmsg):
    name = ndmsg.get_attr('NFTA_EXPR_NAME')
    try:
        expr_cls = NFTA_EXPR_NAME_MAP[name]
    except KeyError:
        raise NotImplementedError(
            "can't load rule expression {0} from netlink {1}".format(name, ndmsg))
    return expr_cls.from_netlink(name, ndmsg.get_attr('NFTA_EXPR_DATA'))


def get_expression_from_dict(d):
    name = d['type']
    if name in NFTA_EXPR_NAME_MAP:
        expr_cls = NFTA_EXPR_NAME_MAP[name]
    else:
        raise NotImplementedError(
            "can't load rule expression {0} from json {1}".format(name, d))
    return expr_cls.from_dict(d)
