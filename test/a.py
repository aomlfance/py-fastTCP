from fastTCP.unification_socket import Maintenance
import os, psutil

app = Maintenance()

p = psutil.Process(os.getpid())

@app.route("hello")
def hello(name: str):
    print(f"当前进程内存: {p.memory_info().rss / 1024 / 1024:.1f} MB")
    return f"Hello World {name}"

from asyncio import run

run(app.serve_forever("127.0.0.1", 8000))