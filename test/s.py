from fastTCP.unification_socket import Maintenance
from asyncio import run

app = Maintenance()
app2 = Maintenance()

def c(__load__):
    print(__load__)
    return __load__

async def main():
    await app.connect('127.0.0.1', 8080)
    await app2.connect("127.0.0.1", 8080)

    app2.provide("b")(c)

    @app2.route("msg")
    def get_msg(b, msg: dict):
        print(msg.get("sender"), msg.get("msg"))
        return "ok"

    res = await app.request("global", "FastTCP")

run(main())
