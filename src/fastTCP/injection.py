from typing import get_origin, get_args, Union, TYPE_CHECKING

import msgpack
import pydantic

if TYPE_CHECKING:
    from .route import Route

import inspect
from types import NoneType, UnionType
from .socket_ import  Socket
from .context import Context
from .utils import name
import logging

logger = logging.getLogger(__name__)

def inject_one(param: inspect.Parameter, ctx: Context, route: Route):
    if param.annotation == Socket:
        return ctx["__socket__"]
    elif param.annotation == Context:
        return ctx

    if param.name in ctx:
        return ctx[param.name]

    if isinstance(param.annotation, type):
        if "__load__" not in ctx:
            ctx.short["__load__"] = msgpack.unpackb(ctx["__message__"].body)

        if isinstance(ctx["__load__"], param.annotation):
            return ctx["__load__"]
        elif issubclass(param.annotation, pydantic.BaseModel):
            try:
                return param.annotation(**ctx["__load__"])
            except pydantic.ValidationError:
                raise

    if param.default != param.empty:
        return param.default
    # 否则是否允许NoneType
    if get_origin(param.annotation) in (UnionType, Union) and NoneType in get_args(param.annotation):
        return None

    raise TypeError(f"{name(route.handler)} 缺少参数{param.name}")

def inject(ctx: Context, route: Route):
    """
    根据路由函数的签名, 选择要注入的参数
    :raise TypeError, pydantic.ValidationError:
    """
    kwargs = {}

    for index, param in enumerate(inspect.signature(route).parameters.values()):
        # Socket, Context的优先级最高, 不允许注入
        kwargs[param.name] = inject_one(param, ctx, route)

    return kwargs