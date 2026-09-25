"""
Layer 2 — 集成测试，需要真实 server + client
"""
import pytest
import asyncio
from src.fastTCP.frame import FastTCPServer
from src.fastTCP.client import ClientFastTCP


PORT_COUNTER = 9100  # 避免端口冲突，每个测试递增


def get_port():
    global PORT_COUNTER
    PORT_COUNTER += 1
    return PORT_COUNTER


@pytest.fixture
def server():
    """每个测试一个独立 server 实例"""
    port = get_port()
    app = FastTCPServer(host="127.0.0.1", port=port, timeout=5)
    yield app


@pytest.mark.asyncio
async def test_basic_request_response(server):
    """最基础的：客户端发请求，服务端返回响应"""
    port = server.port

    @server.route("ping")
    def ping():
        return "pong"

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        cli = ClientFastTCP(host="127.0.0.1", port=port)
        await cli.connect()
        res = await cli.request("ping", {})
        assert res.status_code == 200
        assert res.body.get("data") == "pong"
        await cli.close()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_request_with_body(server):
    """带 body 的请求"""
    port = server.port

    @server.route("echo")
    def echo(ctx):
        return ctx["payload"].body

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        cli = ClientFastTCP(host="127.0.0.1", port=port)
        await cli.connect()
        res = await cli.request("echo", {"msg": "hello"})
        assert res.status_code == 200
        assert res.body.get("data", res.body).get("msg") == "hello"
        await cli.close()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_404_unknown_route(server):
    """未注册的路由应返回 404"""
    port = server.port

    @server.route("exists")
    def exists():
        return "here"

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        cli = ClientFastTCP(host="127.0.0.1", port=port)
        await cli.connect()
        res = await cli.request("nope", {})
        assert res.status_code == 404
        await cli.close()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_before_middleware(server):
    """before 中间件执行"""
    port = server.port

    @server.before("protected")
    def check(ctx):
        ctx["authed"] = True

    @server.route("protected")
    def protected(ctx):
        return "welcome" if ctx.get("authed") else "denied"

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        cli = ClientFastTCP(host="127.0.0.1", port=port)
        await cli.connect()
        res = await cli.request("protected", {})
        assert res.status_code == 200
        assert res.body.get("data") == "welcome"
        await cli.close()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_multiple_requests(server):
    """同一连接发送多个请求"""
    port = server.port

    @server.route("add")
    def add(ctx):
        body = ctx["payload"].body
        return body.get("a", 0) + body.get("b", 0)

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        cli = ClientFastTCP(host="127.0.0.1", port=port)
        await cli.connect()

        r1 = await cli.request("add", {"a": 1, "b": 2})
        assert r1.body.get("data") == 3

        r2 = await cli.request("add", {"a": 10, "b": 20})
        assert r2.body.get("data") == 30

        await cli.close()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_multiple_clients(server):
    """多个客户端同时连接"""
    port = server.port

    @server.route("hello")
    def hello(ctx):
        return f"hello from server"

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        results = []

        async def client_task(name):
            cli = ClientFastTCP(host="127.0.0.1", port=port)
            await cli.connect()
            res = await cli.request("hello", {})
            results.append((name, res.status_code))
            await cli.close()

        await asyncio.gather(
            client_task("c1"),
            client_task("c2"),
            client_task("c3"),
        )

        assert len(results) == 3
        assert all(status == 200 for _, status in results)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_disconnect_handler(server):
    """客户端断开后触发 disconnect 回调"""
    port = server.port
    disconnected = []

    @server.route("hi")
    def hi():
        return "hi"

    @server.on_disconnect
    def on_disconnect():
        disconnected.append(True)

    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    try:
        cli = ClientFastTCP(host="127.0.0.1", port=port)
        await cli.connect()
        await cli.request("hi", {})
        await cli.close()
        await asyncio.sleep(0.5)  # 等 disconnect 处理

        assert len(disconnected) >= 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
