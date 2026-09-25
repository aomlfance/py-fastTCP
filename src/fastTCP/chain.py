from typing import TYPE_CHECKING, Any, Literal
from warnings import warn

if TYPE_CHECKING:
    from .route import Route
    from .context import _Context, Context
    from .response import ResponsePayload

from .response import make_response, default_response

class Chain:
    def __init__(
            self,
            before: list[Route],
            main_route: Route,
            after: list[Route],
            param: dict[str, Any] | None = None
    ):
        self.before = before
        self.main_route = main_route
        self.after = after
        self.param = param or {}

    async def __call__(self, context: Context) -> ResponsePayload:
        context.short.update(self.param)

        for before_route in self.before:
            res = await before_route(context)

            if not res: break
        else:
            res = await self.main_route(context)

            if not res:
                warn(f"{context["payload"].cmd}主路由没有返回响应")
                res = default_response(204)

        res = make_response(res)
        last_res = res

        for after_route in self.after:
            context["response"] = res
            res = await after_route(context)

            if not res:
                res = last_res
            else:
                last_res = res

        return last_res
