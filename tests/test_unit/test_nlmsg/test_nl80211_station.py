from pathlib import Path

import pytest

from pyroute2.common import load_dump
from pyroute2.netlink.nl80211 import (
    NL80211_CMD_NEW_STATION,
    MarshalNl80211,
    nl80211cmd,
)

SAMPLE = 'test_unit/test_nlmsg/iw_station_rsp.dump'


@pytest.fixture
def sta_info():
    with Path(SAMPLE).open("r", encoding="utf-8") as fp:
        data = load_dump(fp)
    msg = next(iter(MarshalNl80211().parse(data)))
    assert msg.get_attr('NL80211_ATTR_MAC') == 'ee:1d:4f:83:1a:5b'
    return msg.get_attr('NL80211_ATTR_STA_INFO')


@pytest.mark.parametrize(
    'attr,value',
    (
        ('NL80211_STA_INFO_CONNECTED_TIME', 3492),
        ('NL80211_STA_INFO_INACTIVE_TIME', 10310),
        ('NL80211_STA_INFO_RX_BYTES', 1198263),
        ('NL80211_STA_INFO_RX_BYTES64', 1198263),
        ('NL80211_STA_INFO_RX_PACKETS', 7983),
        ('NL80211_STA_INFO_SIGNAL', -30),
        ('NL80211_STA_INFO_SIGNAL_AVG', -32),
        ('NL80211_STA_INFO_CHAIN_SIGNAL', [-31, -54, -43, -34]),
        ('NL80211_STA_INFO_ACK_SIGNAL', -31),
        ('NL80211_STA_INFO_ACK_SIGNAL_AVG', -31),
        ('NL80211_STA_INFO_TX_DURATION', 110784),
        ('NL80211_STA_INFO_AIRTIME_WEIGHT', 256),
        ('NL80211_STA_INFO_ASSOC_AT_BOOTTIME', 658909659884),
        ('NL80211_STA_INFO_RX_MPDUS', None),
        ('NL80211_STA_INFO_FCS_ERROR_COUNT', None),
        ('NL80211_STA_INFO_CONNECTED_TO_GATE', None),
        ('NL80211_STA_INFO_AIRTIME_LINK_METRIC', None),
        ('NL80211_STA_INFO_CONNECTED_TO_AS', None),
    ),
)
def test_sta_info(sta_info, attr, value):
    assert sta_info.get_attr(attr) == value


def test_sta_flags(sta_info):
    assert sta_info.get_attr('NL80211_STA_INFO_STA_FLAGS') == {
        'AUTHORIZED': True,
        'AUTHENTICATED': True,
        'ASSOCIATED': True,
        'SHORT_PREAMBLE': False,
        'WME': True,
        'MFP': False,
        'TDLS_PEER': False,
    }


@pytest.mark.parametrize('attr', ('LOCAL_PM', 'PEER_PM', 'NONPEER_PM'))
@pytest.mark.parametrize(
    'value,name',
    (
        (0, 'unknown'),
        (1, 'active'),
        (2, 'light_sleep'),
        (3, 'deep_sleep'),
        (4, 4),
    ),
)
def test_mesh_power_mode(attr, value, name):
    msg = nl80211cmd()
    msg['cmd'] = NL80211_CMD_NEW_STATION
    msg['attrs'] = [
        (
            'NL80211_ATTR_STA_INFO',
            {'attrs': [(f'NL80211_STA_INFO_{attr}', value)]},
        )
    ]
    msg.encode()

    decoded = nl80211cmd(bytes(msg.data))
    decoded.decode()
    assert decoded.get_attr('NL80211_ATTR_STA_INFO').get_attr(attr) == name


def test_tid_stats(sta_info):
    tid_stats = sta_info.get_attr('NL80211_STA_INFO_TID_STATS')
    assert [stats['tid'] for stats in tid_stats] == list(range(17))

    stats = dict(tid_stats[0]['attrs'])
    assert stats['NL80211_TID_STATS_RX_MSDU'] == 3129
    assert stats['NL80211_TID_STATS_TX_MSDU'] == 1
    assert stats['NL80211_TID_STATS_TX_MSDU_RETRIES'] == 0
    assert stats['NL80211_TID_STATS_TX_MSDU_FAILED'] == 0

    txq_stats = dict(stats['NL80211_TID_STATS_TXQ_STATS']['attrs'])
    assert txq_stats['NL80211_TXQ_STATS_BACKLOG_BYTES'] == 0
    assert txq_stats['NL80211_TXQ_STATS_FLOWS'] == 191
    assert txq_stats['NL80211_TXQ_STATS_TX_BYTES'] == 18915
    assert txq_stats['NL80211_TXQ_STATS_TX_PACKETS'] == 191

    stats = dict(tid_stats[16]['attrs'])
    assert stats['NL80211_TID_STATS_TX_MSDU'] == 267
    assert 'NL80211_TID_STATS_TXQ_STATS' not in stats
