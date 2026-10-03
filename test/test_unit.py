"""
Layer 0 — 纯函数/类单元测试，零网络依赖
"""
import pytest
import msgpack
from src.fastTCP.route.match import is_match_cmd, to_pat
from src.fastTCP.route.route import Route, RouteTypes
from src.fastTCP.route.blueprint import RoutesManager
from src.fastTCP.response import make_response, abort_code, abort_args
from src.fastTCP.socket_ import RequestMessage, ResponseMessage, _Socket
from src.fastTCP.context import _Context, Context
from src.fastTCP.request_dq import RequestDequeManager
from src.fastTCP.utils import Async
from src.fastTCP.injection import inject, inject_one
from src.fastTCP.provider import Supplier, Provider
import pydantic
import inspect


# ── match.py ──────────────────────────────────────────────────────────────────

class TestIsMatchCmd:
    def test_plain_cmd_no_match(self):
        assert is_match_cmd("hey") is False
        assert is_match_cmd("user.list") is False

    def test_angle_bracket_match(self):
        assert is_match_cmd("<int:id>") is True
        assert is_match_cmd("user.<str:name>") is True

    def test_wildcard_match(self):
        assert is_match_cmd("*") is True
        assert is_match_cmd("user.*") is True


class TestToPat:
    def test_wildcard_matches_everything(self):
        pat = to_pat("*")
        assert pat.match("anything")
        assert pat.match("hey")
        assert pat.match("")

    def test_int_wildcard(self):
        pat = to_pat("user.<int:id>")
        m = pat.match("user.42")
        assert m
        assert m.group("id") == "42"

    def test_int_wildcard_rejects_non_digit(self):
        pat = to_pat("user.<int:id>")
        assert not pat.match("user.abc")

    def test_str_wildcard(self):
        pat = to_pat("file.<str:name>")
        m = pat.match("file.hello.txt")
        assert m
        assert m.group("name") == "hello.txt"

    def test_uuid_wildcard(self):
        pat = to_pat("<uuid:uid>")
        m = pat.match("550e8400-e29b-41d4-a716-446655440000")
        assert m
        assert m.group("uid") == "550e8400-e29b-41d4-a716-446655440000"

    def test_literal_period_not_treated_as_wildcard(self):
        pat = to_pat("user.list")
        assert pat.match("user.list")
        assert not pat.match("userXlist")


# ── context.py ────────────────────────────────────────────────────────────────

class TestContext:
    def test_long_priority(self):
        ctx = _Context(x=10)
        ctx.short["x"] = 20
        assert ctx["x"] == 10  # long 优先

    def test_short_fallback(self):
        ctx = _Context()
        ctx.short["y"] = 99
        assert ctx["y"] == 99

    def test_get_default(self):
        ctx = _Context()
        assert ctx.get("missing", "fallback") == "fallback"

    def test_contains(self):
        ctx = _Context(a=1)
        assert "a" in ctx
        assert "b" not in ctx

    @pytest.mark.asyncio
    async def test_refresh_clears_short(self):
        ctx = _Context()
        ctx.short["tmp"] = 123
        await ctx.refresh()
        assert "tmp" not in ctx

    def test_missing_key_raises(self):
        ctx = _Context()
        with pytest.raises(IndexError):
            _ = ctx["nope"]

    def test_context_magic_key(self):
        ctx = _Context()
        assert ctx["__context__"] is ctx

    def test_context_magic_key_in_contains(self):
        ctx = _Context()
        assert "__context__" in ctx

    @pytest.mark.asyncio
    async def test_close_clears_long(self):
        ctx = _Context(x=1)
        await ctx.aclose()
        assert "x" not in ctx.long


# ── response.py ───────────────────────────────────────────────────────────────

class TestMakeResponse:
    def test_string_wraps_in_dict(self):
        r = make_response("hello")
        assert r.status_code == 200
        assert msgpack.unpackb(r.body) == "hello"

    def test_dict_passthrough(self):
        r = make_response({"key": "val"})
        assert msgpack.unpackb(r.body) == {"key": "val"}

    def test_tuple_body_and_status(self):
        r = make_response(("err", 404))
        assert r.status_code == 404
        assert msgpack.unpackb(r.body) == "err"

    def test_tuple_single_element(self):
        r = make_response(("ok",))
        assert r.status_code == 200

    def test_none_response_passthrough(self):
        nr = NoneResponse()
        assert make_response(nr) is nr

    def test_response_message_passthrough(self):
        original = ResponseMessage(status_code=201, body=b"raw")
        assert make_response(original) is original

    def test_int_body(self):
        r = make_response(42)
        assert msgpack.unpackb(r.body) == 42

    def test_list_body(self):
        r = make_response([1, 2, 3])
        assert msgpack.unpackb(r.body) == [1, 2, 3]


class TestAbort:
    def test_abort_code_raises(self):
        from src.fastTCP.exceptions import Abort
        with pytest.raises(Abort) as exc_info:
            abort_code(403)
        assert exc_info.value.response.status_code == 403

    def test_abort_args_raises(self):
        from src.fastTCP.exceptions import Abort
        with pytest.raises(Abort) as exc_info:
            abort_args("bad", 422)
        assert exc_info.value.response.status_code == 422


# ── request_dq.py ─────────────────────────────────────────────────────────────

class TestRequestDequeManager:
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self):
        dqm = RequestDequeManager()
        fut = dqm.enqueue()
        assert not fut.done()
        resp = ResponseMessage(status_code=200, body=b"ok")
        dqm.dequeue(resp)
        assert fut.result() is resp

    def test_can_dequeue_empty(self):
        dqm = RequestDequeManager()
        assert not dqm.can_dequeue()

    @pytest.mark.asyncio
    async def test_can_dequeue_after_enqueue(self):
        dqm = RequestDequeManager()
        dqm.enqueue()
        assert dqm.can_dequeue()

    def test_dequeue_empty_raises(self):
        dqm = RequestDequeManager()
        with pytest.raises(IndexError):
            dqm.dequeue(ResponseMessage(status_code=200, body=b""))


# ── provider.py ───────────────────────────────────────────────────────────────

class TestSupplier:
    def test_default_has_context_and_socket(self):
        from src.fastTCP.socket_ import Socket
        supplier = Supplier.default()
        assert supplier.query(Context) is not None
        assert supplier.query(Socket) is not None

    def test_provide_and_query(self):
        supplier = Supplier()

        @supplier.provide("config")
        def get_config():
            return {"debug": True}

        p = supplier.query("config")
        assert p is not None

    def test_provide_by_type(self):
        supplier = Supplier()

        class MyService:
            pass

        @supplier.provide(MyService)
        def get_service():
            return MyService()

        p = supplier.query(MyService)
        assert p is not None

    def test_query_missing_returns_none(self):
        supplier = Supplier()
        assert supplier.query("nonexistent") is None

    def test_default_context_provider_returns_ctx(self):
        supplier = Supplier.default()
        ctx = _Context()
        provider = supplier.query(Context)
        result = provider.handler(ctx)
        assert result is ctx

    def test_default_socket_provider_returns_socket(self):
        from src.fastTCP.socket_ import Socket
        supplier = Supplier.default()
        provider = supplier.query(Socket)
        assert provider is not None


# ── injection.py ──────────────────────────────────────────────────────────────

def _make_ctx_with_message(cmd="test", body=b""):
    """构造带 message 的 context，用于注入测试"""
    ctx = _Context(
        __supplier__=Supplier.default(),
    )
    ctx.short["__message__"] = RequestMessage(cmd=cmd, body=body)
    return ctx


class TestInjection:
    def test_inject_from_context_store(self):
        ctx = _make_ctx_with_message()
        ctx.short["name"] = "alice"

        def handler(name: str): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["name"] == "alice"

    def test_inject_default_value(self):
        ctx = _make_ctx_with_message()

        def handler(n: int = 42): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["n"] == 42

    def test_inject_optional_none(self):
        ctx = _make_ctx_with_message()

        def handler(x: int | None = None): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert "x" in kwargs

    def test_inject_context_via_supplier(self):
        ctx = _make_ctx_with_message()

        def handler(ctx: Context): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["ctx"] is ctx

    def test_inject_pydantic_from_body(self):
        body = msgpack.packb({"x": 1})
        ctx = _make_ctx_with_message(body=body)

        class M(pydantic.BaseModel):
            x: int

        def handler(m: M): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["m"].x == 1

    def test_inject_custom_provider(self):
        supplier = Supplier.default()

        @supplier.provide("greeting")
        def get_greeting(ctx):
            return f"hello from {ctx['__message__'].cmd}"

        ctx = _make_ctx_with_message(cmd="greet")
        ctx.short["__supplier__"] = supplier

        def handler(greeting: str): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["greeting"] == "hello from greet"

    def test_inject_type_based_provider(self):
        supplier = Supplier.default()

        class MyService:
            def __init__(self):
                self.value = 99

        @supplier.provide(MyService)
        def get_service(ctx):
            return MyService()

        ctx = _make_ctx_with_message()
        ctx.short["__supplier__"] = supplier

        def handler(svc: MyService): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["svc"].value == 99

    def test_inject_missing_param_raises(self):
        ctx = _make_ctx_with_message()

        def handler(unknown_param: int): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        with pytest.raises(TypeError):
            inject(ctx, route)


# ── utils.py ──────────────────────────────────────────────────────────────────

class TestAsync:
    @pytest.mark.asyncio
    async def test_wraps_sync_function(self):
        def add(a, b):
            return a + b
        result = await Async(add)(1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_wraps_async_function(self):
        async def add(a, b):
            return a + b
        result = await Async(add)(1, 2)
        assert result == 3
