from typing import Callable, Any

from .context import Context
from .msg import RequestMessage
from .socket_ import Socket
from .utils import TempSignature

def _get_socket(__socket__): return __socket__

def _get_message(__message__): return __message__

def _get_context(__context__): return __context__

class Supplier:
    def __init__(self):
        self._store: dict[type | str, Callable] = {}
        self.matchings: list[tuple[Callable[..., bool], Callable]] = []

    def provide(self, sell: type | str):
        def decorator(handler):
            self._store[sell] = TempSignature(handler)
            return handler
        return decorator

    def match(self, the_inspector: Callable[..., bool]):
        def decorator(handler):
            self.matchings.append((the_inspector, TempSignature(handler)))
            return handler
        return decorator

    def query(self, name_or_type: Any) -> Callable | None:
        if (r1 := self._store.get(name_or_type)) is None:
            for i, t in self.matchings:
                if i(name_or_type):
                    return t
            else:
                return None
        else:
            return r1

    @classmethod
    def default(cls):
        """默认实现由Socket, context, message类型提示 -> 魔法键"""
        obj = cls()
        obj.provide(Socket)(_get_socket)
        obj.provide(Context)(_get_context)
        obj.provide(RequestMessage)(_get_message)
        return obj