import inspect
from enum import Enum
from typing import Callable, ParamSpec, TypeVar, Concatenate
import logging
from .context import Context
from .utils import name
from .chain import Chain

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

def unknown_cmd(ctx):
    return "unknown_cmd", 404

unknown_cmd_route = Route("404", unknown_cmd, RouteTypes.ROUTE)

class RoutesManager:
    """管理路由, 更简单的拼接链"""
    def __init__(self):
        self.all_before: list[Route] = []
        self.before_routes: dict[str, list[Route]] = {}
        self.routes: dict[str, Route] = {}
        self.after_routes: dict[str, list[Route]] = {}
        self.all_after: list[Route] = []
        self._type_all = {RouteTypes.BEFORE_ROUTE: self.all_before, RouteTypes.AFTER_ROUTE: self.all_after}
        self._type_routes = {RouteTypes.BEFORE_ROUTE: self.before_routes, RouteTypes.AFTER_ROUTE: self.after_routes}

    def add_route(self, route: Route):
        match route.type:
            case type_ if type_ in (RouteTypes.BEFORE_ROUTE, RouteTypes.AFTER_ROUTE):
                if route.cmds == ["*"]:
                    self._type_all[type_].append(route)
                else:
                    for cmd in route.cmds:
                        if cmd in self.before_routes:
                            self._type_routes[type_][cmd].append(route)
                        else:
                            self._type_routes[type_][cmd] = [route]
            case RouteTypes.ROUTE:
                for cmd in route.cmds:

                    if cmd in self.routes:
                        logger.warning(f"{cmd}路由重复, {name(route.handler)} 即将覆盖 {name(route.handler)}")

                    self.routes[cmd] = route
            case _:
                raise AssertionError(f"{route.type} 并不在预期中")

    def get_chain(self, cmd: str):
        if cmd not in self.routes:
            return Chain([], unknown_cmd_route, [])

        return Chain(
            [*self.all_before, *self.before_routes.get(cmd, [])],
            self.routes[cmd],
            [*self.after_routes.get(cmd, []), *self.all_after],
        )

    def __getitem__(self, item):
        ...

P = ParamSpec("P")
R = TypeVar("R")

class Blueprint(RoutesManager):
    """蓝图, 在路由管理者的基础上添加注册功能"""
    def _route(self, cmds: list[str] | str, type_: RouteTypes = RouteTypes.ROUTE) -> Callable[
        [
            Callable[Concatenate[Context, P], R]
        ],
        Callable[Concatenate[Context, P], R]
    ]:
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
