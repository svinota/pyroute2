from socket import htons
from common import nla_plus_police
from common import get_filter_police_parameter


def fix_msg(msg, kwarg):
    msg['info'] = htons(kwarg.get('protocol', 0) & 0xffff) |\
            ((kwarg.get('prio', 0) << 16) & 0xffff0000)


def get_parameters(kwarg):
    ret = {'attrs': []}
    attrs_map = (
        ('classid', 'TCA_FW_CLASSID'),
        ('act', 'TCA_FW_ACT'),
        # ('police', 'TCA_FW_POLICE'),
        # Handled in get_filter_police_parameter
        ('indev', 'TCA_FW_INDEV'),
        ('mask', 'TCA_FW_MASK'),
    )

    if kwarg.get('rate'):
        ret['attrs'].append([
            'TCA_FW_POLICE',
            {'attrs': get_filter_police_parameter(kwarg)}
        ])

    for k, v in attrs_map:
        r = kwarg.get(k, None)
        if r is not None:
            ret['attrs'].append([v, r])

    return ret


class options(nla_plus_police):
    nla_map = (('TCA_FW_UNSPEC', 'none'),
               ('TCA_FW_CLASSID', 'uint32'),
               ('TCA_FW_POLICE', 'police'),  # TODO string?
               ('TCA_FW_INDEV', 'hex'),  # TODO string
               ('TCA_FW_ACT', 'hex'),  # TODO
               ('TCA_FW_MASK', 'uint32'))
