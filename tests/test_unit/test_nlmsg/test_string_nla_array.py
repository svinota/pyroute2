# SPDX-License-Identifier: Apache-2.0
#
# Regression test for https://github.com/svinota/pyroute2/issues/1330
#
# NL80211_ATTR_SCAN_SSIDS is declared as *string (an NLA array of strings).
# When the outer NLA is decoded with _nla_array=True, self.value is set to a
# list of child cells by nla_base.decode(). The string.decode() method then
# tried to call self.value.decode('utf-8') on that list, raising:
#
#     AttributeError: 'list' object has no attribute 'decode'
#
# The fix: guard the utf-8 decode with isinstance(self.value, bytes).

import struct

from pyroute2.netlink import nlmsg_atoms


def _build_string_nla_array(*strings):
    """Build a raw NLA payload for an array of strings.

    The outer NLA header is prepended so the result can be passed directly
    to nlmsg_atoms.string(data=...) for decoding.
    """
    payload = bytearray()
    for i, s in enumerate(strings):
        encoded = s.encode('utf-8') if s else b''
        inner_length = 4 + len(encoded)  # 4-byte NLA header
        payload += struct.pack('HH', inner_length, i)
        payload += encoded
        # Pad to 4-byte boundary
        pad = (4 - (inner_length % 4)) % 4
        payload += b'\x00' * pad

    total_length = 4 + len(payload)
    return bytearray(struct.pack('HH', total_length, 0)) + payload


def test_string_nla_array_decode_no_attributeerror():
    """string.decode() with _nla_array=True must not raise AttributeError."""
    buf = _build_string_nla_array('', 'ssid_a', 'ssid_b')
    instance = nlmsg_atoms.string(data=buf, offset=0)
    instance._nla_array = True
    instance.decode()  # must not raise


def test_string_nla_array_value_is_list():
    """After decoding a *string NLA, value must be a list, not raw bytes."""
    buf = _build_string_nla_array('', 'ssid_a')
    instance = nlmsg_atoms.string(data=buf, offset=0)
    instance._nla_array = True
    instance.decode()
    assert isinstance(
        instance.value, list
    ), f"Expected list, got {type(instance.value).__name__}"


def test_string_nla_plain_decode_still_returns_str():
    """Ensure the fix does not break plain (non-array) string decode."""
    text = 'hello'
    encoded = text.encode('utf-8')
    length = 4 + len(encoded)
    buf = bytearray(struct.pack('HH', length, 0)) + bytearray(encoded)
    instance = nlmsg_atoms.string(data=buf, offset=0)
    instance._nla_array = False
    instance.decode()
    assert instance.value == text, f"Expected {text!r}, got {instance.value!r}"
