from fastTCP.unification_socket import FastTCP
from fastTCP.provider import ResponseQ
from fastTCP.socket_ import Socket
from asyncio import run

app = FastTCP()

@app.route("global")
async def hello(res: ResponseQ):
    print(res)

run(app.serve_forever("127.0.0.1", 8080))