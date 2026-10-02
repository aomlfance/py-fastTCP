from fastTCP._unification_socket import Maintenance

app = Maintenance()

@app.route("hello")
def hello():
    return "Hello World"

from asyncio import run

run(app.serve_forever("127.0.0.1", 8000))