import time

import pytest


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
