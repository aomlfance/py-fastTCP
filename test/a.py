from src.fastTCP import FastTCP
from asyncio import run
from socket_ import Socket

app = FastTCP()

@app.route("hey")
async def hey(sock: Socket):
    await sock.request("hey", "none")
    return "hey"

run(app.start())