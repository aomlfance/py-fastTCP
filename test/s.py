from src.fastTCP.client import ClientFastTCP
import asyncio
import logging

logging.basicConfig(level=0)

async def main():
    cli = ClientFastTCP()
    await cli.connect()

    res = await cli.request("hey","FastTCP")
    print(res)

asyncio.run(main())