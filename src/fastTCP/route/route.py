from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import _Context
    from ..response import ResponseMessage
    from ..provider import Supplier
    from ..msg import RequestMessage

from enum import Enum
from re import Pattern
import inspect
import logging

from .match import is_match_cmd, to_pat
from ..response import default_response, make_response
from ..injection import inject
from ..utils import Async
from ..exceptions import Abort, ExitSignal

logger = logging.getLogger(__name__)


class RouteTypes(Enum):
    BEFORE_ROUTE = "before-route"
    ROUTE = "route"
    AFTER_ROUTE = "after-route"
    PROVIDER = "provider"

class Route:
    def __init__(
            self,
            cmds: list[str] | str ,
            handler: Callable,
            type_: RouteTypes,
            echo_log: bool = True
    ):
        _cmds =  cmds if isinstance(cmds, list) else [cmds]

        self.cmds: list[Pattern | str] = []

        for cmd in _cmds:
            if not is_match_cmd(cmd):
                self.cmds.append(cmd)
            else:
                self.cmds.append(to_pat(cmd))

        self.handler = handler
        self.type = type_
        self.echo_log = echo_log

        self._sig = None

    @property
    def __signature__(self):
        if self._sig is None:
            self._sig = inspect.signature(self.handler)
        return self._sig

    async def __call__(self, ctx: _Context, supplier: Supplier, message: RequestMessage) -> ResponseMessage | None:
        """
        :return: 倘若route.type为RouteTypes.ROUTE必定返回ResponsePayload
        """
        result = None

        try:
            injection_kwargs = await inject(ctx, self, supplier, message)

            result = await Async(self.handler)(**injection_kwargs)
        except Abort as e:
            result = e.response
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