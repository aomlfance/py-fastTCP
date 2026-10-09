from typing import TYPE_CHECKING, Protocol, Any, Callable

from types import TracebackType

if TYPE_CHECKING:
    from .provider import Supplier
    from .msg import RequestMessage

import inspect
from .context import _Context, Context
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

class NotCoveredLevel:
    """作用域内为 ctx 补齐缺失的键; 已存在的键一律不覆盖, 退出时只回收自己写入的键."""
    def __init__(self, father: _Context, *args: tuple[str, Any]):
        self.context = father
        self.defaults = dict(args)
        self.mine: set[str] = set()

    def __enter__(self):
        for name, value in self.defaults.items():
            if name not in self.context:
                self.context.short[name] = value
                self.mine.add(name)
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None):
        for name in self.mine:
            self.context.short.pop(name, None)

async def inject_one(param: inspect.Parameter, ctx: _Context, supplier: Supplier):
    # 注入需要什么吗
    # 1.是先查上下文
    # 2.是在是否要提供同名提供者
    # 3.类型判断
    # --先查参数名--
    if param.name in ctx:
        return ctx[param.name]

    with NotCoveredLevel(
            ctx,
            ("__param__", param),
            # 父参数的意思, 即父runner中真实的一个参数, 而非其子判断器|子提供者的参数混淆
            ("__inspector_stack__", []),
            # 判断器栈防止同一个判断器在当前判断路径中递归进入自己
            # ex.: -> 由A判断 -> 查询A首参数A_arg -> 让A判断|(无链) -> 查询A_arg ->
            #                                            |(有栈判断) -> 下一个判断器B
            ("__provider_stack__", [])
            # 提供栈防的是循环依赖(因为提供者也可以被注入)
            # ex.: -> A提供者|(无栈) -> 查询A-arg -> 取得B提供者 -> 查询B_arg -> A判断器
            #               |(有栈, 发现自己被重复依赖, 报错, 否则等到无限递归报错)
            # Note: 判断器返回提供者前会弹出自身，因此 provider 开始执行时
            #       当前这一层判断器不会继续留在 inspector_stack 中
            #       inspector_stack 只描述当前仍在进行的判断器调用路径
        ):
        inspector_stack = ctx["__inspector_stack__"]
        provider_stack  = ctx["__provider_stack__"]

        if provider := (
            supplier.query_by_param(param.name)
            or supplier.query_by_note(param.annotation)
            or await supplier.match(ctx, inspector_stack, provider_stack)
        ):
            if provider in provider_stack:
                raise RuntimeError(f"循环依赖: {provider_stack} + {provider}")

            provider_stack.append(provider)

            try:
                return await call_like_route(provider, ctx, supplier)
            finally:
                provider_stack.pop()

    raise TypeError(
        f"缺少参数{param.name}"
        "包括fastTCP不推荐带默认值的写法"
        "如果要鉴权, 应该在注入函数中短路.",
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
