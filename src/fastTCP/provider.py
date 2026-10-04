from typing import Callable, Any
import msgpack
import pydantic

from .context import Context, _Context
from .msg import RequestMessage, ResponseMessage
from .socket_ import Socket
from .utils import TempSignature
from .injection import call_like_route

async def _get_socket(__socket__): return __socket__

async def _get_message(__message__): return __message__

async def _get_context(__context__): return __context__

async def _get_response(__response__): return __response__

async def _load(ctx: Context, message: RequestMessage):
    if "__load__" in ctx:
        return ctx["__load__"]

    ctx.short["__load__"] = msgpack.unpackb(message.body)

    return ctx.short["__load__"]

async def _return_annotation(__annotation__):
    return __annotation__

async def _can_inject_msg(annotation, __load__):
    return isinstance(annotation, type) and (isinstance(__load__, annotation) or issubclass(annotation, pydantic.BaseModel))

async def _inject_msg(annotation, __load__):
    if isinstance(__load__, annotation):
        return __load__
    else:
        return annotation(**__load__)

class Supplier:
    def __init__(self):
        self._store: dict[type | str, Callable] = {}
        self.matchings: list[tuple[Callable[..., bool], Callable]] = []

    def provide(self, sell: type | str):
        def decorator(handler):
            self._store[sell] = TempSignature(handler)
            return handler
        return decorator

    def match(self, the_inspector):
        def decorator(handler):
            self.matchings.append((TempSignature(the_inspector), TempSignature(handler)))
            return handler
        return decorator

    async def query(self, name_or_type: Any, ctx: _Context) -> Callable | None:
        if (r1 := self._store.get(name_or_type)) is None:
            match_chain: list = ctx["__match_chain__"]

            for i, t in self.matchings:

                if i in match_chain:
                    continue

                match_chain.append(i)

                try:
                    if await call_like_route(i, ctx, self):
                        return t
                finally:
                    del match_chain[-1]

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
        obj.provide(ResponseMessage)(_get_response)
        obj.provide("__load__")(_load)
        obj.provide("annotation")(_return_annotation)
        obj.match(_can_inject_msg)(_inject_msg)
        return obj