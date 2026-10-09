"""驱动 test/a.py: 起 server, 发 global 请求, 打印服务端与客户端结果"""
import asyncio
import sys

sys.path.insert(0, "src")

from fastTCP.unification_socket import FastTCP

app = FastTCP()


@app.route("global")
async def hello(res: str):
    print("HANDLER 收到 res =", res)


async def main():
    server = asyncio.create_task(app.serve_forever("127.0.0.1", 8093))
    await asyncio.sleep(0.3)

    client = FastTCP()
    await client.connect("127.0.0.1", 8093)
    code, body = await client.request("global", "PARAM_VAL")
    print("CLIENT:", code, body)
    server.cancel()


try:
    asyncio.run(main())
except Exception as e:
    print("DRIVER FAIL:", type(e).__name__, e)
