import inspect
from typing import Callable, Any, TypeAlias, Literal, Hashable
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

ArgAnnotation: TypeAlias = type | Any | inspect.Parameter.empty
ArgName: TypeAlias = str | Literal["我没用, 我防hash碰撞"]

async def _can_none_response(ctx: Context):
    return None if (mk := "__response__") not in ctx else ctx[mk]

async def _load(ctx: Context, message: RequestMessage):
    key = "__load__"

    if key not in ctx:
        ctx.short[key] = msgpack.unpackb(message.body)

    return ctx.short[key]

async def _can_inject_msg(param: inspect.Parameter, loaded: Loaded):
    annotation = param.annotation
    try:
        return (
                isinstance(annotation, type)
                and (
                        isinstance(loaded, annotation)
                        or issubclass(annotation, pydantic.BaseModel)
                )
        )
    except TypeError:
        return False

async def _inject_msg(param: inspect.Parameter, loaded: Loaded):
    return loaded if isinstance(loaded, param.annotation) else param.annotation(**loaded)

def _map(key: str):
    async def getter(ctx: Context):
        return ctx[key]
    return getter

class Map:
    def __init__(self, param_name: str = "_", annotation: Any = ...):
        self.__signature__ = inspect.Signature([
            inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)
        ])

    def __call__(self, *args, **kwargs):
        # 注入按参数名传 kwargs(同名上下文注入), 取唯一注入值返回
        if kwargs:
            return next(iter(kwargs.values()))
        return args[0]

class Supplier:
    def __init__(self):
        self.param_store: dict[str, Callable] = {}
        self.note_store: dict[Any, Callable] = {}
        self.matchings: list[tuple[Callable[..., bool], Callable]] = []

    def provide_note(self, note: Hashable):
        """
        提供注解

        Args:
            note: 提供的注解(可hash)

        Returns:
            提供一个其函数的装饰器, 函数义为提供者, 结果会作为注入值
        """
        def decorator(handler):
            self.note_store[note] = TempSignature(handler)
            return handler
        return decorator

    def provide_param(self, param: str):
        """
        提供参数

        Args:
            param: 参数的名字 | 魔法键(__?__格式字符串)

        Returns:
            提供一个其函数的装饰器, 函数义为提供者, 结果会作为注入值
        """
        def decorator(handler):
            self.param_store[param] = TempSignature(handler)
            return handler
        return decorator

    def judgment(self, inspector: Callable):
        """
        判断规则

        Args:
            inspector: 判断者(可被注入)

        Returns:
            返回一个装饰器(接受一个函数的函数),其形参函数(也可以被注入)的返回值会被当作注入的值.
        """
        def decorator(handler):
            self.matchings.append((TempSignature(inspector), TempSignature(handler)))
            return handler
        return decorator

    def query_by_param(self, param_name: str) -> Callable | None:
        return self.param_store.get(param_name)

    def query_by_note(self, note: Hashable) -> Callable | None:
        return self.note_store.get(note)

    async def match(
            self,                 ctx: _Context,
            inspector_stack: list | None = None,
            provider_stack:  list | None = None
    ) -> Callable | None:
        if inspector_stack is None: inspector_stack = []
        if provider_stack  is None: provider_stack  = []

        for i, t in self.matchings:

            if i in inspector_stack or t in provider_stack:
                continue

            inspector_stack.append(i)

            try:
                if await call_like_route(i, ctx, self): return t
            finally:
                inspector_stack.pop()
        else:
            return None

    @classmethod
    def default(cls):
        """
        一个已经实现

        注解Socket -> 魔法键__socket__

        注解Context -> 魔法键__context__

        注解RequestMessage -> 魔法键__message__

        注解ResponseMessage -> 魔法键__response__

        注解ResponseQ(允许判空) -> None | Response

        注解Loaded -> 魔法键__load__ -> 序列化RequestMessgae.body 缓存至 ctx, 返回序列化结果


        """
        obj = cls()
        obj.provide_note(Socket)(Map("__socket__"))
        obj.provide_note(Context)(Map("__context__"))
        obj.provide_note(RequestMessage)(Map("__message__"))

        obj.provide_note(ResponseMessage)(Map("__response__"))
        obj.provide_note(ResponseQ)(_can_none_response)

        obj.provide_param("__load__")(_load)
        obj.provide_note(Loaded)(Map("__load__"))

        obj.provide_note(inspect.Parameter)(Map("__param__"))

        obj.judgment(_can_inject_msg)(_inject_msg)
        return obj
