from fastTCP import FastTCP
from asyncio import run
from fastTCP.socket_ import Socket

app = FastTCP()

@app.route("hey")
async def hey(sock: Socket):
    await sock.request("hey", "none")
    return "hey"

run(app.start())