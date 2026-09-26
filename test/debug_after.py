import asyncio
from fastTCP.server import FastTCPServer
from fastTCP.client import ClientFastTCP

async def test():
    app = FastTCPServer(host='127.0.0.1', port=9300, timeout=5)

    @app.route('original')
    def original():
        return 'first'

    @app.after('original')
    def add_tag(ctx):
        return 'tagged'

    task = asyncio.create_task(app.serve_forever())
    await asyncio.sleep(0.3)

    cli = ClientFastTCP(host='127.0.0.1', port=9300)
    await cli.connect()
    res = await cli.request('original', {})
    print(f'status={res.status_code} body={res.body}')
    await cli.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print('DONE')

asyncio.run(test())
