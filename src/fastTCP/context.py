from types import GenericAlias
from typing import Any, Protocol, get_origin
from .utils import _clear

class Context(Protocol):
    """对外api"""
    long: dict[str | MagicKey, Any]
    short: dict[str | MagicKey, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """
        从上下文中安全取值(类dict.get).优先long再short.
        """
        pass

    def __getitem__(self, item: str) -> Any:
        """
        从上下文中取值(类dict[]).优先long再short.

        Raises:
            KeyError: 当item既不在long, 也不在short时
        """

    def __contains__(self, item: str) -> bool:
        """
        item是否在上下文中.
        """

class MagicKey:
    """
    该类用来与普通上下文键对区分.
    常存储在上下文中.

    用意: 现在的 __?__ 格式很脆弱， 有可能被匹配, 误引用.
    """
    __slots__ = ("name", )

    def __class_getitem__(cls, item: str) -> GenericAlias:
        return GenericAlias(cls, (item,))

    def __init__(self, name):
        self.name = name

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, MagicKey):
            return NotImplemented
        return self.name == value.name

    def __hash__(self) -> int:
        return hash(self.name)

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
        self.long: dict[str | MagicKey, Any] = {}
        self.long.update(kwargs)

        self.short: dict[str | MagicKey, Any] = {}

    def get(self, key: str | MagicKey, default: Any = None) -> Any:
        for m in (self.long, self.short):
            if key in m: return m[key]
        else:
            return default

    def __getitem__(self, item: str | MagicKey) -> Any:
        if item not in self:
            raise IndexError("item not in context")
        else:
            return self.get(item)

    def __contains__(self, item: str | MagicKey) -> bool:
        return item in self.long or item in self.short

    async def refresh(self):
        await _clear(self.short)

    async def aclose(self):
        await self.refresh()

        self.long[MagicKey("in_clearing")] = True # in_end

        try:
            await _clear(self.long)
        finally:
            self.long.pop(MagicKey("in_clearing"), None)

    @classmethod
    def take_self(cls, **kwargs):
        obj = cls(**kwargs)

        not_close_ctx = _NotCloseContext()

        not_close_ctx.long = obj.long
        not_close_ctx.short = obj.short

        obj.long[MagicKey("context")] = not_close_ctx

        return obj

class _NotCloseContext(_Context):
    def close(self):
        if self.get(MagicKey("in_clearing")):
            return
        else:
            raise RuntimeWarning("不得不在父上下文closing时关闭上下文")

    async def aclose(self):
        return self.close()
