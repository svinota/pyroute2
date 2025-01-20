import pytest


@pytest.mark.asyncio
async def test_server_data_read(p9):
    fid = await p9.client.fid('test_file')
    response = await p9.client.read(fid)
    assert response['data'] == p9.sample_data


@pytest.mark.asyncio
async def test_server_data_write(p9):
    new_sample = b'aevei3PhaeGeiseh'
    fid = await p9.client.fid('test_file')
    await p9.client.write(fid, new_sample)
    response = await p9.client.read(fid)
    assert response['data'] == new_sample
    assert new_sample != p9.sample_data
