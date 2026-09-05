import inspect
from enum import Enum
from typing import Callable, ParamSpec, TypeVar, Concatenate, TypeAlias, Any
import logging
from .context import Context
from .utils import name
from .chain import Chain
from re import compile, escape, Pattern

logger = logging.getLogger(__name__)

class RouteTypes(Enum):
    BEFORE_ROUTE = "before-route"
    ROUTE = "route"
    AFTER_ROUTE = "after-route"

class Route:
    def __init__(self, cmds: list[str] | str, handler: Callable, type_: RouteTypes, echo_log: bool = True):
        self.cmds =  cmds if isinstance(cmds, list) else [cmds]
        self.handler = handler
        self.type = type_
        self.echo_log = echo_log
        self.handler_sig = inspect.signature(handler)

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
                type_, name = inner.split(":", 1)
            else:
                type_, name = "str", inner
            regex = TYPE_MAP.get(type_, TYPE_MAP["str"])
            parts.append(f"(?P<{name}>{regex})")
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
            can_match = is_match_cmd(cmd)

            obj = self.dynamic_chains if can_match else self.chains
            cmd = to_pat(cmd) if can_match else cmd

            if cmd not in obj:
                chain = Chain([], unknown_cmd_route, [])
                obj[cmd] = chain
            else:
                chain = obj[cmd]

            if route.type == RouteTypes.ROUTE:
                chain.main_route = route
            elif route.type == RouteTypes.BEFORE_ROUTE:
                chain.before.append(route)
            elif route.type == RouteTypes.AFTER_ROUTE:
                chain.after.append(route)
            else:
                raise TypeError(f"Unknown route type: {route.type}")

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
        def decorator(handler: Callable[Concatenate[Context, P], R]) -> Callable[Concatenate[Context, P], R]:
            route = Route(cmds, handler, type_)
            self.add_route(route)
            return handler
        return decorator

    def before(self, cmds: list[str] | str):
        return self._route(cmds, RouteTypes.BEFORE_ROUTE)

    def route(self, cmds: list[str] | str):
        return self._route(cmds, RouteTypes.ROUTE)

    def after(self, cmds: list[str] | str):
        return self._route(cmds, RouteTypes.AFTER_ROUTE)
