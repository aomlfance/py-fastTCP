from fastTCP.unification_socket import Maintenance
from fastTCP.context import Context


app = Maintenance()

@app.route("hello")
def hello(name: str):
    return f"Hello World {name}"

from asyncio import run

run(app.serve_forever("127.0.0.1", 8000))