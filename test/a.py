from fastTCP.unification_socket import Maintenance
from fastTCP.context import Context
from fastTCP.socket_ import Socket
from asyncio import run

app = Maintenance()

@app.route("global")
async def hello(socket: Socket, msg: str):
    for c in app.conns.values():
        if c["__socket__"] == socket:
            continue
        await c["__socket__"].request("msg", {"sender": socket.address, "msg": msg})
    return "ok"

run(app.serve_forever("127.0.0.1", 8080))