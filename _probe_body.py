"""实测 body 注入的两种写法 + aclose 崩溃复现"""
import asyncio
from fastTCP.unification_socket import FastTCP
from fastTCP.provider import Loaded

PORT = 9318
app = FastTCP()


@app.route("echo_load")
def echo_load(__load__):
    return __load__


@app.route("echo_note")
def echo_note(data: Loaded):
    return data


@app.route("add")
def add(__load__):
    return __load__.get("a", 0) + __load__.get("b", 0)


async def main():
    task = asyncio.create_task(app.serve_forever("127.0.0.1", PORT))
    await asyncio.sleep(0.3)

    cli = FastTCP()
    await cli.connect("127.0.0.1", PORT)

    for cmd, body in [
        ("echo_load", {"msg": "hello"}),
        ("echo_note", {"msg": "world"}),
        ("add", {"a": 1, "b": 2}),
    ]:
        code, b = await asyncio.wait_for(cli.request(cmd, body), 3)
        print(f"{cmd!r:14} -> {code} {b!r}")

    print("--- aclose ---")
    try:
        await cli.aclose()
        print("aclose OK")
    except Exception as e:
        print(f"aclose ERR {type(e).__name__}: {e}")

    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


asyncio.run(main())
