import ctypes
import struct

from pyroute2.netlink import NLA_F_NESTED, nla
from pyroute2.netlink.rtnl.tcmsg.common import tc_actions
from pyroute2.netlink.rtnl.tcmsg.utils import parse_mac

# Pedit masks (0 = write byte, 1 = preserve byte)
PEDIT_MASK_WRITE_ALL = 0x00000000      # Write all 4 bytes
PEDIT_MASK_WRITE_U16_LOW = 0xFFFF0000  # Write lower 2 bytes only
PEDIT_MASK_WRITE_U16_HIGH = 0x0000FFFF # Write upper 2 bytes only

# Pedit NLA attributes
TCA_PEDIT_PARMS_EX = 'TCA_PEDIT_PARMS_EX'
TCA_PEDIT_KEYS_EX = 'TCA_PEDIT_KEYS_EX'
TCA_PEDIT_KEY_EX = 'TCA_PEDIT_KEY_EX'
TCA_PEDIT_KEY_EX_HTYPE = 'TCA_PEDIT_KEY_EX_HTYPE'
TCA_PEDIT_KEY_EX_CMD = 'TCA_PEDIT_KEY_EX_CMD'

ETH_FIELD_OFFSETS = {
    'dst': 0,
    'src': 6,
}


class PeditArgs:
    TC_ACTION = 'tc_action'
    MUNGE = 'munge'

    # Munge operation parameters
    HTYPE = 'htype'
    CMD = 'cmd'
    FIELD = 'field'
    VALUE = 'value'


def _bytes_to_int_le(b):
    """Convert upto 4 bytes to little-endian integer."""
    if len(b) > 4:
        raise ValueError("cannot convert bytes to int, bytes array length > 4")

    b = b + b'\x00' * (4 - len(b))
    return struct.unpack('<I', b)[0]


def get_parameters(kwarg):
    if PeditArgs.TC_ACTION not in kwarg:
        raise ValueError('tc_action is required for pedit action')

    if PeditArgs.MUNGE not in kwarg:
        raise ValueError('munge is required for pedit action')

    action_str = kwarg[PeditArgs.TC_ACTION]
    action_code = tc_actions.get(action_str)
    if action_code is None:
        raise ValueError('unknown tc_action: {}'.format(action_str))

    keys, keys_ex = _process_munge_ops(kwarg[PeditArgs.MUNGE])

    sel = TcPeditSelector(action=action_code, nkeys=len(keys))
    payload = sel.pack() + b''.join(keys)

    attrs = [[TCA_PEDIT_PARMS_EX, payload]]
    if keys_ex:
        attrs.append([TCA_PEDIT_KEYS_EX, {'attrs': _build_keys_ex_attrs(keys_ex)}])

    return {'attrs': attrs}


def _process_munge_ops(munge_ops):
    """
    Process a list of munge operations into pedit keys.

    Each munge op specifies a header type (eth, ip4, etc.) and command
    (set, add). Returns packed keys and extended key metadata.
    """
    keys = []
    keys_ex = []

    for op in munge_ops:
        if not isinstance(op, dict):
            raise ValueError('munge entries must be dicts')

        if PeditArgs.CMD not in op:
            raise ValueError('munge requires cmd parameter')
        cmd = op[PeditArgs.CMD].lower()

        if PeditArgs.HTYPE not in op:
            raise ValueError('munge requires htype parameter')
        htype = op[PeditArgs.HTYPE].lower()

        if cmd not in PEDIT_CMDS:
            raise ValueError('unknown cmd: {}'.format(cmd))
        if htype not in PEDIT_HDR_TYPES:
            raise ValueError('unknown htype: {}'.format(htype))

        if cmd == 'set' and htype == 'eth':
            op_keys, op_keys_ex = _handle_set_eth(op)
            keys.extend(op_keys)
            keys_ex.extend(op_keys_ex)
        else:
            raise NotImplementedError(
                'munge (cmd={}, htype={}) not implemented'.format(cmd, htype)
            )

    return keys, keys_ex


def _handle_set_eth(op):
    """
    Handle 'set' command for ethernet header fields.

    Takes a munge operation dict with 'field' (dst/src) and 'value' (MAC).
    Returns pedit keys to modify the specified MAC in ethernet header.
    """
    if PeditArgs.FIELD not in op:
        raise ValueError('eth set requires field parameter (dst or src)')
    field = op[PeditArgs.FIELD].lower()

    if field not in ETH_FIELD_OFFSETS:
        raise ValueError('eth field must be one of: {}'.format(', '.join(ETH_FIELD_OFFSETS.keys())))

    if PeditArgs.VALUE not in op:
        raise ValueError('eth set requires value parameter')

    mac_bytes = parse_mac(op[PeditArgs.VALUE])
    keys = _eth_mac_to_keys(mac_bytes, field)

    cmd_const = PEDIT_CMDS['set']
    htype_const = PEDIT_HDR_TYPES['eth']
    keys_ex = [{PeditArgs.HTYPE: htype_const, PeditArgs.CMD: cmd_const} for _ in keys]

    return keys, keys_ex


def _eth_mac_to_keys(mac_bytes, field):
    """
    Convert 6-byte MAC to pedit keys.

    Pedit operates on 32-bit aligned words, but MAC is 6 bytes,
    so we need 2 keys to cover it. Mask selects which bytes to modify.
    """
    if field == 'dst':
        return [
            TcPeditKey(mask=PEDIT_MASK_WRITE_ALL, val=_bytes_to_int_le(mac_bytes[0:4]), off=0).pack(),
            TcPeditKey(mask=PEDIT_MASK_WRITE_U16_LOW, val=_bytes_to_int_le(mac_bytes[4:6] + b'\x00\x00'), off=4).pack(),
        ]
    else:
        return [
            TcPeditKey(mask=PEDIT_MASK_WRITE_U16_HIGH, val=_bytes_to_int_le(b'\x00\x00' + mac_bytes[0:2]), off=4).pack(),
            TcPeditKey(mask=PEDIT_MASK_WRITE_ALL, val=_bytes_to_int_le(mac_bytes[2:6]), off=8).pack(),
        ]


def _build_keys_ex_attrs(keys_ex):
    """Build TCA_PEDIT_KEYS_EX nested attribute list."""
    return [
        [
            TCA_PEDIT_KEY_EX,
            {
                'attrs': [
                    [TCA_PEDIT_KEY_EX_HTYPE, ex[PeditArgs.HTYPE]],
                    [TCA_PEDIT_KEY_EX_CMD, ex[PeditArgs.CMD]],
                ]
            },
        ]
        for ex in keys_ex
    ]


# from include/uapi/linux/tc_act/tc_pedit.h
class options(nla):
    nla_flags = NLA_F_NESTED
    nla_map = (
        ('TCA_PEDIT_UNSPEC', 'none'),
        ('TCA_PEDIT_TM', 'none'),
        ('TCA_PEDIT_PARMS', 'cdata'),
        ('TCA_PEDIT_PAD', 'none'),
        ('TCA_PEDIT_PARMS_EX', 'cdata'),
        ('TCA_PEDIT_KEYS_EX', 'keys_ex'),
        ('TCA_PEDIT_KEY_EX', 'none'),
    )

    class keys_ex(nla):
        nla_flags = NLA_F_NESTED
        nla_map = (
            ('TCA_PEDIT_UNSPEC', 'none'),
            ('TCA_PEDIT_TM', 'none'),
            ('TCA_PEDIT_PARMS', 'none'),
            ('TCA_PEDIT_PAD', 'none'),
            ('TCA_PEDIT_PARMS_EX', 'none'),
            ('TCA_PEDIT_KEYS_EX', 'none'),
            ('TCA_PEDIT_KEY_EX', 'key_ex'),
        )

        class key_ex(nla):
            nla_flags = NLA_F_NESTED
            nla_map = (
                ('TCA_PEDIT_KEY_EX_UNSPEC', 'none'),
                ('TCA_PEDIT_KEY_EX_HTYPE', 'uint16'),
                ('TCA_PEDIT_KEY_EX_CMD', 'uint16'),
            )


class TcPeditSelector(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('index', ctypes.c_uint32),
        ('capab', ctypes.c_uint32),
        ('action', ctypes.c_int32),
        ('refcnt', ctypes.c_int32),
        ('bindcnt', ctypes.c_int32),
        ('nkeys', ctypes.c_uint8),
        ('flags', ctypes.c_uint8),
        ('_pad', ctypes.c_uint16),
    ]

    def pack(self):
        return ctypes.string_at(ctypes.addressof(self), ctypes.sizeof(self))


class TcPeditKey(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('mask', ctypes.c_uint32),
        ('val', ctypes.c_uint32),
        ('off', ctypes.c_uint32),
        ('at', ctypes.c_uint32),
        ('offmask', ctypes.c_uint32),
        ('shift', ctypes.c_uint32),
    ]

    def pack(self):
        return ctypes.string_at(ctypes.addressof(self), ctypes.sizeof(self))


PEDIT_HDR_TYPES = {
    'network': 0,
    'eth': 1,
    'ip4': 2,
    'ip6': 3,
    'tcp': 4,
    'udp': 5,
}

PEDIT_CMDS = {
    'set': 0,
    'add': 1,
}
