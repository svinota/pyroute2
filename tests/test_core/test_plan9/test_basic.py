import time

import pytest

from pyroute2.fixtures.plan9 import AsyncPlan9Context


@pytest.mark.asyncio
async def test_server_data_read(async_p9_context):
    fid = await async_p9_context.client.fid('test_file')
    response = await async_p9_context.client.read(fid)
    assert response['data'] == async_p9_context.sample_data


@pytest.mark.asyncio
async def test_server_time_read(async_p9_context):
    ts = time.time_ns()
    fid = await async_p9_context.client.fid('test_time')
    responses = [await async_p9_context.client.read(fid) for _ in range(5)]
    times = {int(x['data'].decode('utf-8')) for x in responses}
    assert len(times) == 5
    assert min(times) > ts
    assert max(times) < time.time_ns()


@pytest.mark.asyncio
async def test_server_data_write(async_p9_context):
    new_sample = b'aevei3PhaeGeiseh'
    fid = await async_p9_context.client.fid('test_file')
    await async_p9_context.client.write(fid, new_sample)
    response = await async_p9_context.client.read(fid)
    assert response['data'] == new_sample
    assert new_sample != async_p9_context.sample_data


@pytest.mark.asyncio
async def test_servers_do_not_share_state():
    # Two servers in one process, each with one client. Each client allocates
    # fids from 1, so the same fid number is live on both connections.
    first = AsyncPlan9Context()
    second = AsyncPlan9Context()
    with second.server.filesystem.create('second_only') as i:
        i.data.write(b'second server data')
    await first.ensure_session()
    await second.ensure_session()
    try:
        fid = await first.client.fid('test_file')
        await second.client.fid('second_only')
        response = await first.client.read(fid)
        assert response['data'] == first.sample_data
        with pytest.raises(KeyError):
            first.server.filesystem.walk('second_only')
    finally:
        first.close()
        second.close()
