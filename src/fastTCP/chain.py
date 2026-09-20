from typing import TYPE_CHECKING, Any
from .context import Context

if TYPE_CHECKING:
    from .route import Route

class Chain:
    def __init__(
            self,
            before: list["Route"],
            main_route: "Route",
            after: list["Route"],
            param: dict[str, Any] | None = None
    ):
        self.before = before
        self.main_route = main_route
        self.after = after
        self.param = param or {}

    def __call__(self, context: Context):
        ...
