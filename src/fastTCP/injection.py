from operator import call
from typing import TYPE_CHECKING, Annotated, Protocol, Any, Callable, get_origin, get_args
from types import GenericAlias

from types import TracebackType

if TYPE_CHECKING:
    from .msg import RequestMessage

import inspect
from .context import _Context, Context
import logging
from .utils import Async
from .exceptions import Abort, ExitSignal

logger = logging.getLogger(__name__)

async def call_like_route(handler: Callable, ctx: _Context):
    # 我也不知道要叫什么名字
    injection_kwargs = await inject(ctx, inspect.signature(handler))

    return await Async(handler)(**injection_kwargs)

async def inject_one(param: inspect.Parameter, ctx: _Context):
    if get_origin(param.annotation) is not Annotated:

        if param.annotation is Context:
            return ctx

        raise TypeError(
            "无法理解的注解类型", param.annotation
        )
    
    provider = get_args(param.annotation)[1]

    return await call_like_route(provider, ctx)

async def inject(ctx: _Context, sig: inspect.Signature):
    # 有意思的是inject注入的必要因素, 不是一定是路由
    # 只要route可以被查签名即可, 是不关心运行的
    # 但注入肯定是要运行的, 不过message是否要以参数传入存疑
    # 有意思的是路由的签名是指向原handler的, 但__call__确需要context, supplier...
    # 实际上是我们吧怎么逻辑搞混了, 是路由的call就包括了注入.
    # 那就是route是对原handler注入, 在调用原handler.
    # 既然签名不是route本身的(会降低可读), 所以直接传入签名不就好了
    kwargs = {}

    for param in sig.parameters.values():
        kwargs[param.name] = await inject_one(param, ctx)

    return kwargs
