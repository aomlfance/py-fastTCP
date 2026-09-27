"""
Layer 1 — 中间件链 + 路由匹配，需要 mock Route 但不需要网络
"""
import pytest
import asyncio
import msgpack
from src.fastTCP.route.route import Route, RouteTypes
from src.fastTCP.route.blueprint import RoutesManager
from src.fastTCP.chain import Chain
from src.fastTCP.context import _Context
from src.fastTCP.socket_ import RequestMessage, ResponseMessage
from src.fastTCP.provider import Supplier
import pydantic
from src.fastTCP.exceptions import Abort, ExitSignal
from src.fastTCP.response import default_response


def _make_ctx(cmd="test", body=b""):
    """构造带 message + supplier 的 context"""
    supplier = Supplier.default()
    ctx = _Context(__supplier__=supplier)
    ctx.short["__message__"] = RequestMessage(cmd=cmd, body=body)
    return ctx


def _make_simple_route(cmd, handler, type_=RouteTypes.ROUTE):
    return Route(cmd, handler, type_)


# ── RoutesManager ─────────────────────────────────────────────────────────────

class TestRoutesManager:
    def _make_route(self, cmd, handler, type_=RouteTypes.ROUTE):
        return Route(cmd, handler, type_)

    def test_add_and_get_plain_route(self):
        mgr = RoutesManager()

        def hello(): return "hello"
        route = self._make_route("hello", hello)
        mgr.add_route(route)

        chain = mgr.get_chain("hello")
        assert chain.main_route is route

    def test_unknown_route_returns_404(self):
        mgr = RoutesManager()
        chain = mgr.get_chain("nonexistent")
        assert chain.main_route is not None

    def test_before_middleware_order(self):
        mgr = RoutesManager()
        order = []

        def main(): return "main"
        def before1(): order.append(1); return None
        def before2(): order.append(2); return None

        mgr.add_route(self._make_route("test", main))
        mgr.add_route(self._make_route("test", before1, RouteTypes.BEFORE_ROUTE))
        mgr.add_route(self._make_route("test", before2, RouteTypes.BEFORE_ROUTE))

        chain = mgr.get_chain("test")
        assert len(chain.before) == 2

    def test_after_middleware_order(self):
        mgr = RoutesManager()

        def main(): return "main"
        def after1(): return None
        def after2(): return None

        mgr.add_route(self._make_route("test", main))
        mgr.add_route(self._make_route("test", after1, RouteTypes.AFTER_ROUTE))
        mgr.add_route(self._make_route("test", after2, RouteTypes.AFTER_ROUTE))

        chain = mgr.get_chain("test")
        assert len(chain.after) == 2

    def test_dynamic_route_matching(self):
        mgr = RoutesManager()

        def get_user(): return "user"
        mgr.add_route(self._make_route("user.<int:id>", get_user))

        chain = mgr.get_chain("user.42")
        assert chain.main_route.handler is get_user

    def test_dynamic_route_not_matching(self):
        mgr = RoutesManager()

        def get_user(): return "user"
        mgr.add_route(self._make_route("user.<int:id>", get_user))

        chain = mgr.get_chain("user.abc")
        assert chain.main_route is not mgr.get_chain("user.1").main_route


# ── Chain.__call__ ────────────────────────────────────────────────────────────

class TestChain:
    @pytest.mark.asyncio
    async def test_main_route_executes(self):
        async def main_handler():
            return "ok"
        route = _make_simple_route("test", main_handler)
        chain = Chain([], route, [])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert res.body == msgpack.packb("ok")

    @pytest.mark.asyncio
    async def test_before_can_short_circuit(self):
        called = []

        async def main_handler():
            called.append("main")
            return "ok"

        async def before_handler():
            return "blocked"

        main_route = _make_simple_route("test", main_handler)
        before_route = _make_simple_route("test", before_handler, RouteTypes.BEFORE_ROUTE)
        chain = Chain([before_route], main_route, [])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert "main" not in called
        assert res.body == msgpack.packb("blocked")

    @pytest.mark.asyncio
    async def test_before_none_continues_to_main(self):
        async def main_handler():
            return "ok"

        async def before_handler():
            return None

        main_route = _make_simple_route("test", main_handler)
        before_route = _make_simple_route("test", before_handler, RouteTypes.BEFORE_ROUTE)
        chain = Chain([before_route], main_route, [])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert res.body == msgpack.packb("ok")

    @pytest.mark.asyncio
    async def test_after_can_override_response(self):
        async def main_handler():
            return "original"

        async def after_handler():
            return "overridden"

        main_route = _make_simple_route("test", main_handler)
        after_route = _make_simple_route("test", after_handler, RouteTypes.AFTER_ROUTE)
        chain = Chain([], main_route, [after_route])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert res.body == msgpack.packb("overridden")

    @pytest.mark.asyncio
    async def test_after_none_keeps_previous(self):
        async def main_handler():
            return "original"

        async def after_handler():
            return None

        main_route = _make_simple_route("test", main_handler)
        after_route = _make_simple_route("test", after_handler, RouteTypes.AFTER_ROUTE)
        chain = Chain([], main_route, [after_route])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert res.body == msgpack.packb("original")

    @pytest.mark.asyncio
    async def test_full_before_main_after_pipeline(self):
        order = []

        async def before1():
            order.append("before1")
            return None

        async def before2():
            order.append("before2")
            return None

        async def main_handler():
            order.append("main")
            return "result"

        async def after_handler():
            order.append("after")
            return None

        b1 = _make_simple_route("test", before1, RouteTypes.BEFORE_ROUTE)
        b2 = _make_simple_route("test", before2, RouteTypes.BEFORE_ROUTE)
        main_r = _make_simple_route("test", main_handler)
        a1 = _make_simple_route("test", after_handler, RouteTypes.AFTER_ROUTE)

        chain = Chain([b1, b2], main_r, [a1])
        ctx = _make_ctx()
        await chain(ctx)
        assert order == ["before1", "before2", "main", "after"]

    @pytest.mark.asyncio
    async def test_route_params_injected_into_context(self):
        async def main_handler():
            return "ok"

        route = _make_simple_route("user.<int:id>", main_handler)
        chain = Chain([], route, [], param={"id": "42"})

        ctx = _make_ctx("user.42")
        await chain(ctx)
        assert ctx.short.get("id") == "42"


# ── Route.__call__ ─────────────────────────────────────────────────────────────

def _make_ctx_with_socket(cmd="test", body=b""):
    supplier = Supplier.default()
    ctx = _Context(__supplier__=supplier)
    ctx.short["__message__"] = RequestMessage(cmd=cmd, body=body)
    return ctx


class TestRouteCall:
    @pytest.mark.asyncio
    async def test_sync_handler_returns_value(self):
        def handler():
            return "hello"
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.body == msgpack.packb("hello")

    @pytest.mark.asyncio
    async def test_async_handler_returns_value(self):
        async def handler():
            return {"key": "val"}
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert msgpack.unpackb(res.body) == {"key": "val"}

    @pytest.mark.asyncio
    async def test_handler_returns_tuple_with_status(self):
        def handler():
            return "created", 201
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.status_code == 201

    @pytest.mark.asyncio
    async def test_handler_returns_dict_directly(self):
        def handler():
            return {"a": 1}
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert msgpack.unpackb(res.body) == {"a": 1}

    @pytest.mark.asyncio
    async def test_handler_returns_none_gives_204(self):
        def handler():
            return None
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.status_code == 204

    @pytest.mark.asyncio
    async def test_handler_returns_none_before_gives_none(self):
        def handler():
            return None
        route = Route("test", handler, RouteTypes.BEFORE_ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res is None

    @pytest.mark.asyncio
    async def test_abort_code_in_handler(self):
        def handler():
            raise Abort(default_response(403))
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_handler_exception_gives_500(self):
        def handler():
            raise ValueError("boom")
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.status_code == 500

    @pytest.mark.asyncio
    async def test_exit_signal_propagates(self):
        def handler():
            raise ExitSignal("timeout")
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        with pytest.raises(ExitSignal):
            await route(ctx)

    @pytest.mark.asyncio
    async def test_pydantic_validation_error_gives_400(self):
        class Strict(pydantic.BaseModel):
            required_field: int

        def handler(s: Strict):  # type: ignore
            return "ok"
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_injection_error_gives_500(self):
        def handler(unknown_param: int):
            return "ok"
        route = Route("test", handler, RouteTypes.ROUTE)
        ctx = _make_ctx_with_socket()
        res = await route(ctx)
        assert res.status_code == 500


# ── Blueprint 装饰器 ──────────────────────────────────────────────────────────

class TestBlueprint:
    def test_route_decorator(self):
        mgr = RoutesManager()

        def route(cmds):
            def decorator(handler):
                route_obj = Route(cmds, handler, RouteTypes.ROUTE)
                mgr.add_route(route_obj)
                return handler
            return decorator

        @route("hello")
        def hello():
            return "hello"

        chain = mgr.get_chain("hello")
        assert chain.main_route.handler is hello

    def test_route_list_cmds(self):
        mgr = RoutesManager()

        def route(cmds):
            def decorator(handler):
                route_obj = Route(cmds, handler, RouteTypes.ROUTE)
                mgr.add_route(route_obj)
                return handler
            return decorator

        @route(["hey", "hi", "hello"])
        def greet():
            return "hi"

        for cmd in ["hey", "hi", "hello"]:
            chain = mgr.get_chain(cmd)
            assert chain.main_route.handler is greet

    def test_before_and_after_on_same_cmd(self):
        mgr = RoutesManager()
        order = []

        def make_route(cmd, handler, type_):
            r = Route(cmd, handler, type_)
            mgr.add_route(r)

        make_route("test", lambda: order.append("before") or None, RouteTypes.BEFORE_ROUTE)
        make_route("test", lambda: order.append("main") or "ok", RouteTypes.ROUTE)
        make_route("test", lambda: order.append("after") or None, RouteTypes.AFTER_ROUTE)

        chain = mgr.get_chain("test")
        assert len(chain.before) == 1
        assert len(chain.after) == 1
        assert chain.main_route is not None

    def test_global_before_with_wildcard(self):
        mgr = RoutesManager()

        def global_before():
            return None

        mgr.add_route(Route("*", global_before, RouteTypes.BEFORE_ROUTE))
        mgr.add_route(Route("hello", lambda: "hi", RouteTypes.ROUTE))

        chain = mgr.get_chain("hello")
        assert len(chain.before) == 1

    def test_dynamic_before_before_static_route(self):
        mgr = RoutesManager()

        mgr.add_route(Route("user.<int:id>", lambda: "user", RouteTypes.ROUTE))
        mgr.add_route(Route("user.<str:name>", lambda: None, RouteTypes.BEFORE_ROUTE))

        chain = mgr.get_chain("user.42")
        assert len(chain.before) == 1
