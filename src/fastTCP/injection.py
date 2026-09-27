from typing import get_origin, get_args, Union, TYPE_CHECKING

import msgpack
import pydantic

if TYPE_CHECKING:
    from .route import Route

import inspect
from types import NoneType, UnionType
from .context import Context
from .utils import name
import logging

logger = logging.getLogger(__name__)

def inject_one(param: inspect.Parameter, ctx: Context, route: Route):
    # 1. context store 里有没有
    if param.name in ctx:
        return ctx[param.name]

    # 2. supplier 按名字查
    if provider := ctx["__supplier__"].query(param.name):
        return provider(ctx)

    # 3. 默认值
    if param.default != param.empty:
        return param.default

    # 4. pydantic BaseModel → 从 body 反序列化绑定
    if isinstance(param.annotation, type) and issubclass(param.annotation, pydantic.BaseModel):
        if "__load__" not in ctx:
            ctx.short["__load__"] = msgpack.unpackb(ctx["__message__"].body)
        return param.annotation(**ctx["__load__"])

    # 5. supplier 按类型查
    if isinstance(param.annotation, type):
        if provider := ctx["__supplier__"].query(param.annotation):
            return provider(ctx)

    # 6. Optional → None
    if get_origin(param.annotation) in (UnionType, Union) and NoneType in get_args(param.annotation):
        return None

    raise TypeError(f"{name(route.handler)} 缺少参数{param.name}")

def inject(ctx: Context, route: Route):
    """
    根据路由函数的签名, 选择要注入的参数
    :raise TypeError, pydantic.ValidationError:
    """
    kwargs = {}

    for param in inspect.signature(route).parameters.values():
        kwargs[param.name] = inject_one(param, ctx, route)

    return kwargs
