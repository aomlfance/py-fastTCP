from typing import Callable, Any, TypeAlias, Literal
import msgpack
import pydantic

from .context import Context, _Context
from .msg import RequestMessage, ResponseMessage
from .socket_ import Socket
from .utils import TempSignature
from .injection import call_like_route
from datetime import datetime

ResponseQ: TypeAlias = ResponseMessage | None # ResponseQ的意思是允许判空

Loaded: TypeAlias = (
        Literal[0, False, True] | list[Any] | Any | tuple[Any] | int |
        None | dict[Any, Any] | bytes | Any | str | float | pydantic.BaseModel |
        datetime | msgpack.ext.Timestamp | msgpack.ext.ExtType | bytearray
)

Annotation: TypeAlias = type | Any

async def _can_none_response(ctx: Context):
    return None if "__response__" not in ctx else ctx["__response__"]

async def _load(ctx: Context, message: RequestMessage):
    ctx.short["__load__"] = msgpack.unpackb(message.body)
    return ctx.short["__load__"]

async def _can_inject_msg(annotation: Annotation, loaded: Loaded):
    try:
        return isinstance(annotation, type) and (isinstance(loaded, annotation) or issubclass(annotation, pydantic.BaseModel))
    except TypeError:
        return False

async def _inject_msg(annotation: Annotation, loaded: Loaded):
    return loaded if isinstance(loaded, annotation) else annotation(**loaded)

def _map(key:str):
    return eval(f"lambda {key}:{key}")

class Supplier:
    def __init__(self):
        self._store: dict[Any, Callable] = {}
        self.matchings: list[tuple[Callable[..., bool], Callable]] = []

    def provide(self, sell: Any):
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
        obj.provide(Socket)(_map("__socket__"))
        obj.provide(Context)(_map("__context__"))
        obj.provide(RequestMessage)(_map("__message__"))

        obj.provide(ResponseMessage)(_map("__response__"))
        obj.provide(ResponseQ)(_can_none_response)

        obj.provide("__load__")(_load)
        obj.provide(Loaded)(_map("__load__"))

        obj.provide(Annotation)(_map("__annotation__"))

        obj.match(_can_inject_msg)(_inject_msg)
        return obj