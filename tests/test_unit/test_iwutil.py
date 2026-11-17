import asyncio
from unittest.mock import AsyncMock

import pytest

from pyroute2.iwutil import AsyncIW
from pyroute2.netlink import NLM_F_DUMP, NLM_F_REQUEST
from pyroute2.netlink.nl80211 import (
    BSS_STATUS_NAMES,
    NL80211_NAMES,
    nl80211cmd,
)


@pytest.mark.parametrize(
    'status', (None, 'authenticated', 'associated', 'ibss_joined')
)
def test_get_associated_bss(monkeypatch, status):
    async def check():
        closed = []
        other = nl80211cmd()
        result = nl80211cmd()
        bss = nl80211cmd.bss()
        if status is not None:
            bss['attrs'] = [['NL80211_BSS_STATUS', BSS_STATUS_NAMES[status]]]
        result['attrs'] = [['NL80211_ATTR_BSS', bss]]

        async def responses():
            try:
                yield other
                yield result
                if status in ('associated', 'ibss_joined'):
                    pytest.fail('continued reading after the associated BSS')
            finally:
                closed.append(True)

        async with AsyncIW() as iw:
            iw._prid = 42
            request = AsyncMock(return_value=responses())
            monkeypatch.setattr(iw, 'nlm_request', request)
            associated = await iw.get_associated_bss(7)
            if status in ('associated', 'ibss_joined'):
                assert associated is result
            else:
                assert associated is None
            assert closed == [True]
            request.assert_awaited_once()
            msg = request.call_args.args[0]
            assert msg['cmd'] == NL80211_NAMES['NL80211_CMD_GET_SCAN']
            assert msg.get_attr('NL80211_ATTR_IFINDEX') == 7
            assert request.call_args.kwargs == {
                'msg_type': 42,
                'msg_flags': NLM_F_REQUEST | NLM_F_DUMP,
            }

    asyncio.run(check())
