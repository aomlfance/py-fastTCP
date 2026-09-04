from .socket import Socket
from .payload import RequestPayload
from typing import Any

class Context:
    def __init__(
            self,
            aom_socket: Socket,
            payload: RequestPayload
    ):
        self.socket = aom_socket
        self.payload = payload
        self.store: dict[str, Any] = {}

    def set(self, key: str, value: Any):
        """
        使用该函数, 会为之后的路由注入参数.

        Example:
            @app.before("hello")
            def get_user_name(ctx):
                user_name = ...
                ctx.set("user_name", user_name)
                # 又或者是 ctx["user_name"] = user_name

            @app.on("hello")
            def hello(ctx, user_name):
                return f"hello {user_name}"
        """
        self.store[key] = value

    __setitem__ = set

    def remove(self, key: str):
        """
        会移除在set设置的参数, 防止影响之后的函数
        """
        try:
            del self.store[key]
        except KeyError:
            raise

    __delitem__ = remove

    def get(self, key: str) -> Any | None:
        return self.store.get(key)

    __getitem__ = lambda s, k: s.store[k]

    def __contains__(self, item):
        return item in self.store