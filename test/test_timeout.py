import asyncio
import pytest

from src.fastTCP import FastTCP, ClientFastTCP

# 用列表记录回调是否触发（协程/回调里改局部变量不可见）
events = []

ser = FastTCP(timeout=5)  # 按库的实际参数改

@ser.route("test_timeout")
def timeout():
    return "failure"

@ser.on_disconnect
def on_disconnect():
    events.append("disconnected")
    print("成功")


async def client():
    await asyncio.sleep(0.5)          # 等服务端起来
    cli = ClientFastTCP()
    await cli.connect()   # 按库的实际连接 API 改
    # 故意不发任何消息，等待服务端超时
    await asyncio.sleep(8)

async def run_scenario():
    server_task = asyncio.create_task(ser.start())
    try:
        await client()
    finally:
        server_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await server_task

@pytest.mark.asyncio
async def test_disconnect_on_timeout():
    events.clear()
    server_task = asyncio.create_task(ser.start())
    try:
        await client()
    finally:
        server_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await server_task

    assert "disconnected" in events