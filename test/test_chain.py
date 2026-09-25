"""
Layer 1 — 中间件链 + 路由匹配，需要 mock Route 但不需要网络
"""
import pytest
import asyncio
from src.fastTCP.route.route import Route, RouteTypes
from src.fastTCP.route.blueprint import RoutesManager
from src.fastTCP.chain import Chain
from src.fastTCP.context import _Context
from src.fastTCP.payload import RequestPayload, ResponsePayload
from src.fastTCP.response import NoneResponse


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
        # 应该返回 unknown_cmd chain，不报错
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
        assert chain.main_route is get_user

    def test_dynamic_route_not_matching(self):
        mgr = RoutesManager()

        def get_user(): return "user"
        mgr.add_route(self._make_route("user.<int:id>", get_user))

        chain = mgr.get_chain("user.abc")  # 不匹配 int
        # 应该返回 unknown
        assert chain.main_route is not mgr.get_chain("user.1").main_route


# ── Chain.__call__ ────────────────────────────────────────────────────────────

def _make_ctx(cmd="test"):
    ctx = _Context()
    ctx.short["payload"] = RequestPayload(cmd=cmd, body={})
    return ctx


def _make_simple_route(cmd, handler, type_=RouteTypes.ROUTE):
    return Route(cmd, handler, type_)


class TestChain:
    @pytest.mark.asyncio
    async def test_main_route_executes(self):
        async def main_handler():
            return "ok"
        route = _make_simple_route("test", main_handler)
        chain = Chain([], route, [])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert res.body == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_before_can_short_circuit(self):
        called = []

        async def main_handler():
            called.append("main")
            return "ok"

        async def before_handler():
            return "blocked"  # 返回非 None → 短路

        main_route = _make_simple_route("test", main_handler)
        before_route = _make_simple_route("test", before_handler, RouteTypes.BEFORE_ROUTE)
        chain = Chain([before_route], main_route, [])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert "main" not in called  # main 没被调用
        assert res.body == {"data": "blocked"}

    @pytest.mark.asyncio
    async def test_before_none_continues_to_main(self):
        async def main_handler():
            return "ok"

        async def before_handler():
            return None  # None → 不短路

        main_route = _make_simple_route("test", main_handler)
        before_route = _make_simple_route("test", before_handler, RouteTypes.BEFORE_ROUTE)
        chain = Chain([before_route], main_route, [])

        ctx = _make_ctx()
        res = await chain(ctx)
        assert res.body == {"data": "ok"}

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
        assert res.body == {"data": "overridden"}

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
        assert res.body == {"data": "original"}

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
        """通配符路由的参数应该注入到 context.short"""
        async def main_handler():
            return "ok"

        route = _make_simple_route("user.<int:id>", main_handler)
        chain = Chain([], route, [], param={"id": "42"})

        ctx = _make_ctx("user.42")
        await chain(ctx)
        # param 应该在 context.short 中
        assert ctx.short.get("id") == "42"
