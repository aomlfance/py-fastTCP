from typing import TYPE_CHECKING, Protocol, Any, Callable

if TYPE_CHECKING:
    from provider import Supplier
    from msg import RequestMessage

import inspect
from .context import _Context
import logging
from .utils import Async
from .exceptions import ExitSignal, Abort

logger = logging.getLogger(__name__)

class NeedInJectObject(Protocol):
    @property
    def __signature__(self) -> inspect.Signature: ...

    async def __call__(self, ctx: _Context, supplier: Supplier, message: RequestMessage) -> Any: ...

async def call_like_route(handler: Callable, ctx: _Context, supplier: Supplier):
    # 我也不知道要叫什么名字
    try:
        injection_kwargs = await inject(ctx, inspect.signature(handler), supplier)

        return await Async(handler)(**injection_kwargs)
    except Abort as e:
        return e.response
    except ExitSignal:
        raise

async def inject_one(param: inspect.Parameter, ctx: _Context, supplier: Supplier):
    # 注入需要什么吗
    # 1.是先查上下文
    # 2.是在是否要提供同名提供者
    # 3.类型判断--对消息体检验(这一部分我看看能不能通过自定义规则强调)
    # --先查参数名--
    if param.name in ctx:
        return ctx[param.name]

    if provider := supplier.query(param.name):
        return await call_like_route(provider, ctx, supplier)

    if provider := supplier.query(param.annotation):
        return await call_like_route(provider, ctx, supplier)

    raise TypeError(
        f"缺少参数{param.name}"
        "包括fastTCP不推荐带默认值的写法"
        "如果要鉴权, 应该在注入函数中短路."
    )

async def inject(ctx: _Context, sig: inspect.Signature, supplier: Supplier):
    # 有意思的是inject注入的必要因素, 不是一定是路由
    # 只要route可以被查签名即可, 是不关心运行的
    # 但注入肯定是要运行的, 不过message是否要以参数传入存疑
    # 有意思的是路由的签名是指向原handler的, 但__call__确需要context, supplier...
    # 实际上是我们吧怎么逻辑搞混了, 是路由的call就包括了注入.
    # 那就是route是对原handler注入, 在调用原handler.
    # 既然签名不是route本身的(会降低可读), 所以直接传入签名不就好了
    kwargs = {}

    for param in sig.parameters.values():
        kwargs[param.name] = await inject_one(param, ctx, supplier)

    return kwargs
