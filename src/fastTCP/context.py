from .socket_ import Socket
from .payload import RequestPayload
from typing import Any
from warnings import warn

class Context:

    default_endure = 256

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
            ctx[arg] = value
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

    def __getitem__(self, item: str):
        return self.store[item]

    def __contains__(self, item):
        return item in self.store