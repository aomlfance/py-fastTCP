"""
Layer 2 — 集成测试，需要真实 server + client
"""
import pytest
import asyncio
from src.fastTCP.unification_socket import FastTCP
from src.fastTCP.context import Context


PORT_COUNTER = 47200  # 避开常用段(9210被外部进程占用过)


def get_port():
    global PORT_COUNTER
    PORT_COUNTER += 1
    return PORT_COUNTER


@pytest.fixture
def server():
    port = get_port()
    app = FastTCP()
    app.port = port
    yield app


async def _run_test(server, test_fn, *args, **kwargs):
    """启动 server → 执行 test_fn → 安全清理"""
    task = asyncio.create_task(server.serve_forever("127.0.0.1", server.port))
    await asyncio.sleep(0.2)
    try:
        return await test_fn(server, *args, **kwargs)
    finally:
        await server.aclose()   # 关闭所有连接上下文
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=2)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass


async def _client(srv):
    cli = FastTCP()
    await cli.connect("127.0.0.1", srv.port)
    return cli


# ── 基础请求/响应 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_basic_request_response(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("ping", {})
        assert code == 200
        assert body == "pong"
        await cli.aclose()

    @server.route("ping")
    def ping():
        return "pong"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_request_with_dict_body(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("echo", {"msg": "hello"})
        assert code == 200
        assert body.get("msg") == "hello"
        await cli.aclose()

    @server.route("echo")
    def echo(__load__):
        return __load__

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_request_with_pydantic_model(server):
    from pydantic import BaseModel

    class User(BaseModel):
        name: str
        age: int

    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("register", User(name="alice", age=25))
        assert code == 200
        assert body == "alice,25"
        await cli.aclose()

    @server.route("register")
    def register(user: User):
        return f"{user.name},{user.age}"

    await _run_test(server, _test)


# ── 路由匹配 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_404_unknown_route(server):
    async def _test(srv):
        cli = await _client(srv)
        code, _ = await cli.request("nope", {})
        assert code == 404
        await cli.aclose()

    @server.route("exists")
    def exists():
        return "here"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_wildcard_int_route(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("user.42", {})
        assert code == 200
        assert body == "user_42"
        await cli.aclose()

    @server.route("user.<int:id>")
    def get_user(id: int):
        return f"user_{id}"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_wildcard_str_route(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("file.doc.txt", {})
        assert code == 200
        assert body == "file:doc.txt"
        await cli.aclose()

    @server.route("file.<str:name>")
    def get_file(name: str):
        return f"file:{name}"

    await _run_test(server, _test)


# ── 中间件 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_before_middleware_passes_through(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("protected", {})
        assert code == 200
        assert body == "welcome"
        await cli.aclose()

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
        cli = await _client(srv)
        code, body = await cli.request("blocked", {})
        assert body == "forbidden"
        assert len(main_called) == 0
        await cli.aclose()

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
        cli = await _client(srv)
        code, body = await cli.request("test_ts", {})
        assert code == 200
        assert body == 12345
        await cli.aclose()

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
        cli = await _client(srv)
        code, body = await cli.request("original", {})
        assert body == "tagged"
        await cli.aclose()

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
        cli = await _client(srv)

        _, b1 = await cli.request("add", {"a": 1, "b": 2})
        assert b1 == 3

        _, b2 = await cli.request("add", {"a": 10, "b": 20})
        assert b2 == 30

        _, b3 = await cli.request("add", {"a": 100, "b": 200})
        assert b3 == 300

        await cli.aclose()

    @server.route("add")
    def add(__load__):
        return __load__.get("a", 0) + __load__.get("b", 0)

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_multiple_clients(server):
    async def _test(srv):
        results = []

        async def client_task(name):
            cli = await _client(srv)
            code, body = await cli.request("hello", {})
            results.append((name, code, body))
            await cli.aclose()

        await asyncio.gather(
            client_task("c1"),
            client_task("c2"),
            client_task("c3"),
        )

        assert len(results) == 3
        assert all(code == 200 and body == "hello" for _, code, body in results)

    @server.route("hello")
    def hello():
        return "hello"

    await _run_test(server, _test)


# ── 断开连接 ──────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="on_disconnect 尚未在 FastTCP 中实现")
@pytest.mark.asyncio
async def test_disconnect_handler_fires(server):
    disconnected = []

    async def _test(srv):
        cli = await _client(srv)
        await cli.request("hi", {})
        await cli.aclose()
        await asyncio.sleep(0.5)
        assert len(disconnected) >= 1

    @server.route("hi")
    def hi():
        return "hi"

    @server.on_disconnect
    def on_disconnect():
        disconnected.append(True)

    await _run_test(server, _test)


@pytest.mark.skip(reason="服务端 timeout 断开 + on_disconnect 均未实现")
@pytest.mark.asyncio
async def test_client_timeout_triggers_disconnect(server):
    disconnected = []

    async def _test(srv):
        cli = await _client(srv)
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
        cli = await _client(srv)
        code, body = await cli.request("str", {})
        assert body == "hello"
        await cli.aclose()

    @server.route("str")
    def str_resp():
        return "hello"

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_return_dict_direct_body(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("dict", {})
        assert body == {"key": "value", "count": 42}
        await cli.aclose()

    @server.route("dict")
    def dict_resp():
        return {"key": "value", "count": 42}

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_return_tuple_body_and_status(server):
    async def _test(srv):
        cli = await _client(srv)
        code, body = await cli.request("created", {})
        assert code == 201
        assert body == "resource"
        await cli.aclose()

    @server.route("created")
    def created():
        return "resource", 201

    await _run_test(server, _test)


@pytest.mark.asyncio
async def test_return_none_gives_204(server):
    async def _test(srv):
        cli = await _client(srv)
        code, _ = await cli.request("empty", {})
        assert code == 204
        await cli.aclose()

    @server.route("empty")
    def empty():
        return None

    await _run_test(server, _test)
