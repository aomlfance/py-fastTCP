from typing import Callable, TYPE_CHECKING
if TYPE_CHECKING:
    from ..context import _Context
    from ..response import ResponseMessage
    from ..provider import Supplier

from enum import Enum
from re import Pattern
import logging

from .match import is_match_cmd, to_pat
from ..response import default_response, make_response
from ..utils import TempSignature
from ..injection import call_like_route
from ..exceptions import ExitSignal

logger = logging.getLogger(__name__)

class RouteTypes(Enum):
    BEFORE_ROUTE = "before-route"
    ROUTE = "route"
    AFTER_ROUTE = "after-route"

class Route:
    def __init__(
            self,
            cmds: list[str] | str ,
            handler: Callable,
            type_: RouteTypes,
    ):
        self.handler = TempSignature(handler)

        _cmds = cmds if (isinstance(cmds, list)) else [cmds]

        self.cmds: list[Pattern | str] = []

        for cmd in _cmds:
            if not is_match_cmd(cmd):
                self.cmds.append(cmd)
            else:
                self.cmds.append(to_pat(cmd))

        self.type = type_

    async def __call__(self, ctx: _Context, supplier: Supplier) -> ResponseMessage | None:
        """
        :return: 倘若route.type为RouteTypes.ROUTE必定返回ResponsePayload
        """
        result = None

        try:
            result = await call_like_route(self.handler, ctx, supplier)
        except ExitSignal:
            raise
        except Exception as e:
            logger.error(f"{type(e)} - {e}")
            result = default_response(500)

        if result is None:
            if self.type == RouteTypes.ROUTE:
                result = default_response(204)
        else:
            result = make_response(result)

        ctx.short["__response__"] = result
        return result

def UNKNOWN_CMD():
    return "unknown_cmd", 404
