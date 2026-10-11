from fastTCP.unification_socket import FastTCP
from asyncio import run

app = FastTCP()

async def main():
    await app.connect('127.0.0.1', 8080)

    await app.request("/hello", "str")

run(main())
