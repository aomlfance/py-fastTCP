"""
Layer 2 — 集成测试，需要真实 server + client
"""
import pytest
import asyncio
from src.fastTCP.frame import FastTCPServer
from src.fastTCP.client import ClientFastTCP
from src.fastTCP.context import Context


PORT_COUNTER = 9200


def get_port():
    global PORT_COUNTER
    PORT_COUNTER += 1
    return PORT_COUNTER


@pytest.fixture
def server():
    port = get_port()
    app = FastTCPServer(host="127.0.0.1", port=port, timeout=1)
    yield app


async def _run_test(server, test_fn, *args, **kwargs):
    """启动 server → 执行 test_fn → 安全清理"""
    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)
    try:
        return await test_fn(server, *args, **kwargs)
    finally:
        # 先关闭所有客户端连接，让 handle_client 协程退出
        for addr in list(server.clients.keys()):
            ctx = server.clients.get(addr)
            if ctx:
                socket = ctx.get("socket")
                if socket:
                    try:
                        await socket.close()
                    except Exception:
                        pass
        server.clients.clear()
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=2)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        # 等待残留 handle_client 协程因 timeout 退出
        await asyncio.sleep(1.5)


# ── 基础请求/响应 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_basic_request_response(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("ping", {})
        assert res.status_code == 200
        assert res.body.get("data") == "pong"
        await cli.close()

    @server.route("ping")
    def ping():
        return "pong"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_request_with_dict_body(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("echo", {"msg": "hello"})
        assert res.status_code == 200
        assert res.body.get("msg") == "hello"
        await cli.close()

    @server.route("echo")
    def echo(ctx: Context):
        return ctx["payload"].body

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_request_with_pydantic_model(server):
    from pydantic import BaseModel

    class User(BaseModel):
        name: str
        age: int

    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("register", User(name="alice", age=25))
        assert res.status_code == 200
        assert res.body.get("data") == "alice,25"
        await cli.close()

    @server.route("register")
    def register(user: User):
        return f"{user.name},{user.age}"

    await _run_test(server, _test)


# ── 路由匹配 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_404_unknown_route(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("nope", {})
        assert res.status_code == 404
        await cli.close()

    @server.route("exists")
    def exists():
        return "here"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_wildcard_int_route(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("user.42", {})
        assert res.status_code == 200
        assert res.body.get("data") == "user_42"
        await cli.close()

    @server.route("user.<int:id>")
    def get_user(id: int):
        return f"user_{id}"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_wildcard_str_route(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("file.doc.txt", {})
        assert res.status_code == 200
        assert res.body.get("data") == "file:doc.txt"
        await cli.close()

    @server.route("file.<str:name>")
    def get_file(name: str):
        return f"file:{name}"

    await _run_test(server, _test)


# ── 中间件 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_before_middleware_passes_through(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("protected", {})
        assert res.status_code == 200
        assert res.body.get("data") == "welcome"
        await cli.close()

    @server.before("protected")
    def check(ctx: Context):
        ctx.short["authed"] = True

    @server.route("protected")
    def protected(ctx: Context):
        return "welcome" if ctx.get("authed") else "denied"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_before_middleware_short_circuits(server):
    main_called = []

    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("blocked", {})
        assert res.body.get("data") == "forbidden"
        assert len(main_called) == 0
        await cli.close()

    @server.before("blocked")
    def deny(ctx: Context):
        return "forbidden"

    @server.route("blocked")
    def blocked():
        main_called.append(True)
        return "should not reach"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_global_before_with_wildcard(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("test_ts", {})
        assert res.status_code == 200
        assert res.body.get("data") == 12345
        await cli.close()

    @server.before("*")
    def add_timestamp(ctx: Context):
        ctx.short["ts"] = 12345

    @server.route("test_ts")
    def test_ts(ctx: Context):
        return ctx.get("ts")

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_after_middleware_can_modify_response(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("original", {})
        assert res.body.get("data") == "tagged"
        await cli.close()

    @server.route("original")
    def original():
        return "first"

    @server.after("original")
    def add_tag(ctx: Context):
        return "tagged"

    await _run_test(server, _test)


# ── 多请求/多客户端 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_requests_same_connection(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()

        r1 = await cli.request("add", {"a": 1, "b": 2})
        assert r1.body.get("data") == 3

        r2 = await cli.request("add", {"a": 10, "b": 20})
        assert r2.body.get("data") == 30

        r3 = await cli.request("add", {"a": 100, "b": 200})
        assert r3.body.get("data") == 300

        await cli.close()

    @server.route("add")
    def add(ctx: Context):
        body = ctx["payload"].body
        return body.get("a", 0) + body.get("b", 0)

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_multiple_clients(server):
    async def _test(srv):
        results = []

        async def client_task(name):
            cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
            await cli.connect()
            res = await cli.request("hello", {})
            results.append((name, res.status_code, res.body.get("data")))
            await cli.close()

        await asyncio.gather(
            client_task("c1"),
            client_task("c2"),
            client_task("c3"),
        )

        assert len(results) == 3
        assert all(status == 200 and data == "hello" for _, status, data in results)

    @server.route("hello")
    def hello():
        return "hello"

    await _run_test(server, _test)


# ── 断开连接 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disconnect_handler_fires(server):
    disconnected = []

    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        await cli.request("hi", {})
        await cli.close()
        await asyncio.sleep(0.5)
        assert len(disconnected) >= 1

    @server.route("hi")
    def hi():
        return "hi"

    @server.on_disconnect
    def on_disconnect():
        disconnected.append(True)

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_client_timeout_triggers_disconnect(server):
    disconnected = []

    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        # 不发任何消息，等服务端超时
        await asyncio.sleep(4)
        assert "disconnected" in disconnected

    @server.route("noop")
    def noop():
        return "noop"

    @server.on_disconnect
    def on_disconnect():
        disconnected.append("disconnected")

    await _run_test(server, _test)


# ── 返回值格式 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_return_string_auto_wraps(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("str", {})
        assert res.body == {"data": "hello"}
        await cli.close()

    @server.route("str")
    def str_resp():
        return "hello"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_return_dict_direct_body(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("dict", {})
        assert res.body == {"key": "value", "count": 42}
        await cli.close()

    @server.route("dict")
    def dict_resp():
        return {"key": "value", "count": 42}

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_return_tuple_body_and_status(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("created", {})
        assert res.status_code == 201
        assert res.body == {"data": "resource"}
        await cli.close()

    @server.route("created")
    def created():
        return "resource", 201

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_return_none_gives_204(server):
    async def _test(srv):
        cli = ClientFastTCP(host="127.0.0.1", port=srv.port)
        await cli.connect()
        res = await cli.request("empty", {})
        assert res.status_code == 204
        await cli.close()

    @server.route("empty")
    def empty():
        return None

    await _run_test(server, _test)
