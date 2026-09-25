from re import Pattern
from .route import Route
from ..chain import Chain
from .route import RouteTypes

def unknown_cmd():
    return "unknown_cmd", 404

unknown_cmd_route = Route("404", unknown_cmd, RouteTypes.ROUTE)

unknown_cmd_chain = Chain([], unknown_cmd_route, [])

class RoutesManager:
    """管理路由, 更简单的拼接链"""
    def __init__(self):
        self.chains: dict[str, Chain] = {}

        self.dynamic_before: dict[Pattern, list[Route]] = {}
        self.dynamic_after: dict[Pattern, list[Route]] = {}

        self.dynamic_routes: dict[Pattern, Route] = {}

    def add_route(self, route: Route):
        for cmd in route.cmds:
            if isinstance(cmd, Pattern):

                if route.type == RouteTypes.BEFORE_ROUTE:

                    if cmd not in self.dynamic_before:
                        self.dynamic_before[cmd] = [route]
                    else:
                        self.dynamic_before[cmd].append(route)

                elif route.type == RouteTypes.ROUTE:
                    self.dynamic_routes[cmd] = route

                elif route.type == RouteTypes.AFTER_ROUTE:

                    if cmd not in self.dynamic_after:
                        self.dynamic_after[cmd] = [route]
                    else:
                        self.dynamic_after[cmd].append(route)
            else:
                if cmd not in self.chains:
                    self.chains[cmd] = Chain([], unknown_cmd_route, [])

                chain = self.chains[cmd]

                if route.type == RouteTypes.BEFORE_ROUTE:
                    chain.before.append(route)
                elif route.type == RouteTypes.ROUTE:
                    chain.main_route = route
                elif route.type == RouteTypes.AFTER_ROUTE:
                    chain.after.append(route)

    def get_chain(self, cmd: str):
        params = None

        if _chain := self.chains.get(cmd):
            chain = _chain
        else:
            for pat, _route in self.dynamic_routes.items():
                match = pat.match(cmd)

                if not match:
                    continue

                chain = Chain([], _route, [])
                params = match.groupdict()

                break
            else:
                chain = unknown_cmd_chain

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


class Blueprint(RoutesManager):
    """蓝图, 在路由管理者的基础上添加注册功能"""
    def _route(self, cmds: list[str] | str, type_: RouteTypes = RouteTypes.ROUTE) :

        def decorator_(handler):
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
