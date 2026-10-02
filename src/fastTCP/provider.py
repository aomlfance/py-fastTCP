from typing import Callable

from .context import Context
from .msg import RequestMessage
from .route import Route, RouteTypes
from .socket_ import Socket

class Provider(Route):
    def __init__(self, sell: type | str, handler: Callable):
        self.sell = sell
        self.handler = handler
        self.type = RouteTypes.PROVIDER
        self._sig = None

def _get_socket(__socket__): return __socket__

def _get_message(__message__): return __message__

def _get_context(__context__): return __context__

class Supplier:
    def __init__(self):
        self._store: dict[type | str, Provider] = {}

    def provide(self, sell: type | str):
        def decorator(handler):
            p = Provider(sell, handler)
            self._store[p.sell] = p
            return handler

        return decorator

    def query(self, name_or_type: type | str) -> Provider | None:
        return self._store.get(name_or_type)

    @classmethod
    def default(cls):
        """默认实现由Socket, context, message类型提示 -> 魔法键"""
        obj = cls()
        obj.provide(Socket)(_get_socket)
        obj.provide(Context)(_get_context)
        obj.provide(RequestMessage)(_get_message)
        return obj