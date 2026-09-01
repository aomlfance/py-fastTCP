from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .route import Route

class Chain:
    def __init__(
            self,
            before: list["Route"],
            main_route: "Route",
            after: list["Route"],
    ):
        self.before = before
        self.main_route = main_route
        self.after = after