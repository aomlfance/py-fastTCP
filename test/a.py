import asyncio
from fastTCP import FastTCPServer
app = FastTCPServer()

@app.route("hey")
def hey():
    return "hey"

asyncio.run(app.serve_forever())