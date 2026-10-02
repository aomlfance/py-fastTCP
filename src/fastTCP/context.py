from typing import Any, Protocol, Literal
from .utils import _clear

class Context(Protocol):
    """对外api"""
    long: dict[str, Any]
    short: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any: ...
    def __getitem__(self, item: str) -> Any: ...
    def __contains__(self, item: str) -> bool: ...
    # 关于set, 与del
    # 必须显式申明生命周期

class _Context:
    # 1.
    # ! 并不是你在把东西都装在上下文都万事大吉
    # 我仍推荐在函数签名显式声明参数, 而不是乱七八糟都装到上下文
    # 上下文仅仅特指业务, 而非内核
    # 2.
    # _Context并非我们通常理解的socket对应的生命周期(使_Context与socket解耦)
    # Socket只是将生命周期寄托在了_Context
    # 这是因为_Context作为一个注入的必要形参以注入
    # 不妨这么说_Context本来就就是为注入而生
    # 那么__socket__也可以理解了, 就是为了注入
    # 所以provide也只是为了处理_Context无法处理的形参
    # 这么想的话， 那供应商就不应该存在于_Context, 应该作为一个专门的形参传入注入
    def __init__(self, **kwargs):
        self.long: dict[str, Any] = {}
        self.long.update(kwargs)

        self.short: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        for m in (self.long, self.short):
            if key in m: return m[key]
        else:
            return default

    def __getitem__(self, item: str) -> Any:
        if item not in self:
            raise IndexError("item not in context")
        else:
            return self.get(item)

    def __contains__(self, item: str) -> bool:
        return item in self.long or item in self.short

    async def refresh(self):
        await _clear(self.short)

    async def close(self):
        await self.refresh()
        await _clear(self.long)

    def __getattr__(self, item: Literal["message", "load", "response", "socket"]):
        return self[f"__{item}__"]

