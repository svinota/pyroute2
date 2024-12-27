import asyncio
import json
import threading
from functools import partial

from pyroute2.plan9 import Plan9Exit
from pyroute2.plan9.client import Plan9ClientSocket
from pyroute2.plan9.server import Plan9ServerSocket

address = ('127.0.0.1', 8149)


def stop_server(context):
    if 'task' in context:
        context['task'].cancel()
        raise Plan9Exit(
            '{"status": 200, "message": "shutting down the server"}'
        )
    return '{"status": 503, "message": "server is not ready, try again later"}'


async def server(address, server_started, sample_data):
    p9 = Plan9ServerSocket(address=address)
    context = {}
    # data file
    i_data = p9.filesystem.create('data')
    i_data.data.write(sample_data)
    # shutdown file
    i_stop = p9.filesystem.create('stop')
    i_stop.publish_function(partial(stop_server, context), loader=lambda x: {})
    # save the server task
    context['task'] = await p9.async_run()
    server_started.set()
    try:
        await context['task']
    except asyncio.exceptions.CancelledError:
        pass


def server_thread(address, server_started, sample_data):
    asyncio.run(server(address, server_started, sample_data))


class AsyncPlan9Context:

    server = None
    client = None
    shutdown_response = None
    sample_data = b'Pi6raTaXuzohdu7n'

    def __init__(self):
        self.server_started = threading.Event()
        self.server = threading.Thread(
            target=server_thread,
            args=(address, self.server_started, self.sample_data),
        )
        self.server.start()
        self.server_started.wait()

    async def ensure_client(self):
        self.client = Plan9ClientSocket(address=address)
        await self.client.start_session()

    async def close(self):
        shutdown_file = await self.client.fid('stop')
        await self.client.write(shutdown_file, '')
        try:
            await self.client.read(shutdown_file)
        except Exception as e:
            assert json.loads(e.args[0])['status'] == 200
            self.shutdown_response = e.args[0]
        self.server.join()
