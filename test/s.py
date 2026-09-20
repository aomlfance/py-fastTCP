from src.fastTCP.client import ClientFastTCP
import asyncio

async def main():
    cli = ClientFastTCP()

    @cli.route("hey")
    def hey():
        print("被访问")
        return "hey"

    await cli.connect()

    res = await cli.request("hey", "nihao!")
    print(res)

asyncio.run(main())