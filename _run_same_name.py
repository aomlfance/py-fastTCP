"""验证同名上下文注入: 参数名 = 魔法键字符串, 不走注解"""
import asyncio
import sys

sys.path.insert(0, "src")
from fastTCP.unification_socket import FastTCP

app = FastTCP()


@app.route("same")
async def hello(__socket__, __message__):
    print("HANDLER __socket__ =", type(__socket__).__name__)
    print("HANDLER __message__ =", type(__message__).__name__)
    return "OK"


async def main():
    server = asyncio.create_task(app.serve_forever("127.0.0.1", 8094))
    await asyncio.sleep(0.3)
    client = FastTCP()
    await client.connect("127.0.0.1", 8094)
    code, body = await client.request("same", "")
    print("CLIENT:", code, body)
    server.cancel()


try:
    asyncio.run(main())
except Exception as e:
    print("DRIVER FAIL:", type(e).__name__, e)
