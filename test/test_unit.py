"""
Layer 0 — 纯函数/类单元测试，零网络依赖
"""
import pytest
from src.fastTCP.route.match import is_match_cmd, to_pat
from src.fastTCP.route.route import Route, RouteTypes
from src.fastTCP.route.blueprint import RoutesManager
from src.fastTCP.response import make_response, abort_code, abort_args, NoneResponse
from src.fastTCP.payload import RequestPayload, ResponsePayload
from src.fastTCP.request import make_requests
from src.fastTCP.context import _Context, Context
from src.fastTCP.request_dq import RequestDequeManager
from src.fastTCP.utils import Async
from src.fastTCP.injection import inject
import pydantic


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


# ── payload.py ────────────────────────────────────────────────────────────────

class TestPayload:
    def test_request_payload(self):
        p = RequestPayload(cmd="hey", body={"name": "test"})
        assert p.cmd == "hey"
        assert p.body == {"name": "test"}

    def test_response_payload(self):
        p = ResponsePayload(status_code=200, body={"msg": "ok"})
        assert p.status_code == 200

    def test_request_payload_rejects_missing_cmd(self):
        with pytest.raises(pydantic.ValidationError):
            RequestPayload(body={})


# ── request.py ────────────────────────────────────────────────────────────────

class TestMakeRequests:
    def test_from_string(self):
        req = make_requests("hey", "hello")
        assert req.cmd == "hey"
        assert req.body == {"data": "hello"}

    def test_from_dict(self):
        req = make_requests("hey", {"key": "val"})
        assert req.body == {"key": "val"}

    def test_from_pydantic_model(self):
        class M(pydantic.BaseModel):
            name: str
        req = make_requests("hey", M(name="test"))
        assert req.body == {"name": "test"}

    def test_from_request_payload_passthrough(self):
        original = RequestPayload(cmd="hey", body={"a": 1})
        result = make_requests("other", original)
        assert result is original  # 原样返回，不复制


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

    def test_refresh_clears_short(self):
        ctx = _Context()
        ctx.short["tmp"] = 123
        ctx.refresh()
        assert "tmp" not in ctx

    def test_missing_key_raises(self):
        ctx = _Context()
        with pytest.raises(IndexError):
            _ = ctx["nope"]


# ── response.py ───────────────────────────────────────────────────────────────

class TestMakeResponse:
    def test_string_wraps_in_dict(self):
        r = make_response("hello")
        assert r.body == {"data": "hello"}
        assert r.status_code == 200

    def test_dict_passthrough(self):
        r = make_response({"key": "val"})
        assert r.body == {"key": "val"}

    def test_tuple_body_and_status(self):
        r = make_response(("err", 404))
        assert r.body == {"data": "err"}
        assert r.status_code == 404

    def test_tuple_single_element(self):
        r = make_response(("ok",))
        assert r.status_code == 200

    def test_none_response_passthrough(self):
        nr = NoneResponse()
        assert make_response(nr) is nr


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
        import asyncio
        dqm = RequestDequeManager()
        fut = dqm.enqueue()
        assert not fut.done()
        resp = ResponsePayload(status_code=200, body={"data": "ok"})
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
            dqm.dequeue(ResponsePayload(status_code=200, body={}))


# ── injection.py ──────────────────────────────────────────────────────────────

class TestInjection:
    def test_inject_context(self):
        ctx = _Context()
        ctx.short["payload"] = RequestPayload(cmd="test", body={})

        def handler(ctx: Context): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert "ctx" in kwargs
        assert kwargs["ctx"] is ctx

    def test_inject_from_context_store(self):
        ctx = _Context()
        ctx.short["payload"] = RequestPayload(cmd="test", body={})
        ctx.short["name"] = "alice"

        def handler(name: str): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["name"] == "alice"

    def test_inject_pydantic_from_body(self):
        ctx = _Context()
        ctx.short["payload"] = RequestPayload(cmd="test", body={"x": 1})

        class M(pydantic.BaseModel):
            x: int

        def handler(m: M): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["m"].x == 1

    def test_inject_default_value(self):
        ctx = _Context()
        ctx.short["payload"] = RequestPayload(cmd="test", body={})

        def handler(n: int = 42): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        assert kwargs["n"] == 42

    def test_inject_optional_none(self):
        ctx = _Context()
        ctx.short["payload"] = RequestPayload(cmd="test", body={})

        def handler(x: int | None = None): pass
        route = Route("test", handler, RouteTypes.ROUTE)
        kwargs = inject(ctx, route)
        # 可以是 None 或者默认值，取决于实现
        assert "x" in kwargs


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
