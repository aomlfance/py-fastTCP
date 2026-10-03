from typing import TYPE_CHECKING, Any
from warnings import warn

if TYPE_CHECKING:
    from .route import Route
    from .context import _Context
    from .msg import ResponseMessage
    from .provider import Supplier
    from .msg import RequestMessage

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

    async def __call__(self, context: _Context, supplier: Supplier, message: RequestMessage) -> ResponseMessage:
        context.short.update(self.param)
        context.short["__message__"] = message

        for before_route in self.before:
            res = await before_route(context, supplier, message)

            if res is not None: break
        else:
            res = await self.main_route(context, supplier, message)

        res = make_response(res)
        last_res = res

        for after_route in self.after:
            res = await after_route(context, supplier, message)

            if res is None:
                res = last_res
            else:
                last_res = res

        return last_res
