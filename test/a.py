from fastTCP.unification_socket import FastTCP
from asyncio import run

app = FastTCP()

@app.route("global")
async def hello(res: str):
    print(res)

run(app.serve_forever("127.0.0.1", 8080))