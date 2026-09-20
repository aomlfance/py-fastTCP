from src.fastTCP import FastTCPServer
from asyncio import run
from src.fastTCP.socket_ import Socket

app = FastTCPServer()

@app.route("hey")
async def hey(sock: Socket):
    await sock.request("hey", "none")
    return "hey"

run(app.serve_forever())