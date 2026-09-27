import asyncio
from src.fastTCP import FastTCPServer
app = FastTCPServer()

@app.route("hey")
def hey(name: str):
    return f"hey {name}"

asyncio.run(app.serve_forever())