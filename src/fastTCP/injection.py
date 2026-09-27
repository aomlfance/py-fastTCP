from typing import TYPE_CHECKING

import msgpack
import pydantic

if TYPE_CHECKING:
    from .route import Route

import inspect
from .context import Context
from .utils import name
import logging

logger = logging.getLogger(__name__)

async def inject_one(param: inspect.Parameter, ctx: Context, route: Route):
    # --先查参数名--
    if param.annotation == Context:
        return ctx
    elif param.name in ctx:
        return ctx[param.name]

    if provider := ctx["__supplier__"].query(param.name):
        return await provider(ctx)

    # --类型检查--

    be_type = isinstance(param.annotation, type)

    if be_type and (provider := ctx["__supplier__"].query(param.annotation)):
            return await provider(ctx)

    if "__load__" not in ctx:
        ctx.short["__load__"] = msgpack.unpackb(ctx["__message__"].body)

    if be_type and isinstance(ctx["__load__"], param.annotation):
        return ctx["__load__"]
    elif be_type and issubclass(param.annotation, pydantic.BaseModel):
        return param.annotation(**ctx["__load__"])

    raise TypeError(
        f"{name(route.handler)} 缺少参数{param.name}"
        "包括fastTCP不推荐带默认值的写法"
        "如果要鉴权, 应该在注入函数中短路."
    )

async def inject(ctx: Context, route: Route):
    """
    根据路由函数的签名, 选择要注入的参数
    :raise TypeError, pydantic.ValidationError:
    """
    kwargs = {}

    for param in inspect.signature(route).parameters.values():
        kwargs[param.name] = await inject_one(param, ctx, route)

    return kwargs
