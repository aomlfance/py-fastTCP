from fastTCP.unification_socket import Maintenance
from asyncio import run

app = Maintenance()

async def main():
    await app.connect('127.0.0.1', 8000)

    res = await app.request("hello", "FastTCP")

    print(res)

run(main())