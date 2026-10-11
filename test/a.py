from fastTCP.unification_socket import FastTCP, Message
from fastTCP.context import Context
from asyncio import run

app = FastTCP()

@app.route("/hello")
async def hello(
    msg: Message[dict]
):
    print(msg)

run(app.serve_forever("127.0.0.1", 8080))