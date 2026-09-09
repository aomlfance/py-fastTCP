from fastTCP.client import ClientFastTCP
import asyncio

async def main():
    c = await ClientFastTCP.create()

asyncio.run(main())
