import logging
import inspect
from enum import Enum
from re import compile, escape, Pattern

from typing import Callable, ParamSpec, TypeVar, TypeAlias, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import _Context, Context
    from .chain import Chain
    from .response import Response

from .response import NoneResponse, make_response
from .injection import injection
from .response import default_response
import pydantic
from .utils import Async
from .exceptions import Abort, ExitSignal

logger = logging.getLogger(__name__)

class RouteTypes(Enum):
    BEFORE_ROUTE = "before-route"
    ROUTE = "route"
    AFTER_ROUTE = "after-route"

class Route:
    def __init__(
            self,
            cmds: list[str] | str,
            handler: Callable,
            type_: RouteTypes,
            echo_log: bool = True
    ):
        self.cmds =  cmds if isinstance(cmds, list) else [cmds]
        self.handler = handler
        self.type = type_
        self.echo_log = echo_log
        self.handler_sig = inspect.signature(handler)

    async def __call__(self, ctx: Context) -> Response:
        result = None

        try:
            try:
                injection_kwargs = injection(ctx, self)
            except TypeError as e:
                logger.error(f"{type(e)} - {e}")
                return default_response(500)
            except pydantic.ValidationError as e:
                return default_response(400)

            result = await Async(self.handler)(**injection_kwargs)
        except Abort as e:
            result = e.response
        except ExitSignal:
            raise
        except BaseException as e:
            logger.error(f"{type(e)} - {e}")
            result = default_response(500)

        if result is None:
            if self.type == RouteTypes.ROUTE:
                result = default_response(204)
            else:
                result = NoneResponse()
        else:
            result = make_response(result)

        return result



def unknown_cmd():
    return "unknown_cmd", 404

unknown_cmd_route = Route("404", unknown_cmd, RouteTypes.ROUTE)
angle_bracket_pat = compile("<(.*?)>")

# 通配规则
# standards_format: <type:arg_name>
# 1. <type:(arg_name)>
# 2. <(str:)arg_name> or <:agr_name>
# 3. * 也表示 <str:>

TYPE_MAP = {
    "uuid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "str": ".+",
    "int": r"\d+"
}

def is_match_cmd(cmd: str) -> bool:
    return "<" in cmd or "*" in cmd

def to_pat(cmd: str) -> Pattern[Any]:
    if cmd == "*":
        return compile("^.*$")

    parts = []
    i = 0

    while i < len(cmd):
        if cmd[i] == "<":
            end = cmd.index(">", i)
            inner = cmd[i+1:end]
            if ":" in inner:
                type_, name_ = inner.split(":", 1)
            else:
                type_, name_ = "str", inner
            regex = TYPE_MAP.get(type_, TYPE_MAP["str"])
            parts.append(f"(?P<{name_}>{regex})")
            i = end + 1
        else:
            parts.append(escape(cmd[i]))
            i += 1

    return compile(f"^{''.join(parts)}$")

class RoutesManager:
    """管理路由, 更简单的拼接链"""
    def __init__(self):
        self.chains: dict[str, Chain] = {}

        self.dynamic_before: dict[Pattern, list[Route]] = {}
        self.dynamic_after: dict[Pattern, list[Route]] = {}

        self.dynamic_chains: dict[Pattern, Chain] = {}

    def add_route(self, route: Route):
        for cmd in route.cmds:
            ...

    def get_chain(self, cmd: str):
        params = None

        if _chain := self.chains.get(cmd):
            chain = _chain
        else:
            for pat, _chain in self.dynamic_chains.items():
                match = pat.match(cmd)
                if not match:
                    continue
                chain = _chain
                params = match.groupdict()
                break
            else:
                chain = Chain([], unknown_cmd_route, [])

        before = []
        after = []

        for dict_ in (self.dynamic_before, self.dynamic_after):
            for pat, route_list in dict_.items():
                if not pat.match(cmd):
                    continue
                for route in route_list:
                    if dict_ is self.dynamic_before:
                        before.append(route)
                    else:
                        after.append(route)

        return Chain([*before, *chain.before], chain.main_route, [*chain.after, *after], params)

P = ParamSpec("P")
R = TypeVar("R")

decorator: TypeAlias = Callable[[Callable[P, R]], Callable[P, R]]

class Blueprint(RoutesManager):
    """蓝图, 在路由管理者的基础上添加注册功能"""
    def _route(self, cmds: list[str] | str, type_: RouteTypes = RouteTypes.ROUTE) -> decorator:

        def decorator_(handler: Callable[P, R]) -> Callable[P, R]:
            route = Route(cmds, handler, type_)
            self.add_route(route)
            return handler

        return decorator_

    def before(self, cmds: list[str] | str):
        return self._route(cmds, RouteTypes.BEFORE_ROUTE)

    def route(self, cmds: list[str] | str):
        return self._route(cmds, RouteTypes.ROUTE)

    def after(self, cmds: list[str] | str):
        return self._route(cmds, RouteTypes.AFTER_ROUTE)
