import inspect
from enum import Enum
from typing import Any, Callable, ParamSpec, TypeVar, Concatenate
import logging
from .context import Context

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

def name(obj: Any) -> str:
    return obj.__name__ if hasattr(obj, "__name__") else str(obj)

class Chain:
    def __init__(
            self,
            before: list[Route],
            main_route: Route,
            after: list[Route],
    ):
        self.before = before
        self.main_route = main_route
        self.after = after

class RoutesManager:
    """管理路由, 更简单的拼接链"""
    def __init__(self):
        self.before_routes: dict[str, list[Route]] = {}
        self.routes: dict[str, Route] = {}
        self.after_routes: dict[str, list[Route]] = {}

    def add_route(self, route: Route):
        match route.type:
            case RouteTypes.BEFORE_ROUTE:
                for cmd in route.cmds:
                    if cmd in self.before_routes:
                        self.before_routes[cmd].append(route)
                    else:
                        self.before_routes[cmd] = [route]
            case RouteTypes.ROUTE:
                for cmd in route.cmds:

                    if cmd in self.routes:
                        logger.warning(f"{cmd}路由重复, {name(route.handler)} 即将覆盖 {name(route.handler)}")

                    self.routes[cmd] = route
            case RouteTypes.AFTER_ROUTE:
                for cmd in route.cmds:
                    if cmd in self.after_routes:
                        self.after_routes[cmd].append(route)
                    else:
                        self.after_routes[cmd] = [route]
            case _:
                raise AssertionError(f"{route.type} 并不在预期中")

    def get_chain(self, cmd: str):
        if cmd not in self.routes:
            return Chain([], unknown_cmd_route, [])

        return Chain(self.before_routes.get(cmd, []), self.routes[cmd], self.after_routes.get(cmd, []))

P = ParamSpec("P")
R = TypeVar("R")

class Blueprint(RoutesManager):
    """蓝图, 在路由管理者的基础上添加注册功能"""
    def route(self, cmds: list[str] | str, type_: RouteTypes = RouteTypes.ROUTE) -> Callable[
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
        return self.route(cmds, RouteTypes.BEFORE_ROUTE)

    def on(self, cmds: list[str] | str):
        return self.route(cmds, RouteTypes.ROUTE)

    def after(self, cmds: list[str] | str):
        return self.route(cmds, RouteTypes.AFTER_ROUTE)
