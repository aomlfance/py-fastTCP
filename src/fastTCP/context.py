from typing import Any, Protocol, Self
from warnings import warn
from .utils import Async

class Context(Protocol):
    """对外api"""
    long: dict[str, Any]
    short: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any: ...
    def __getitem__(self, item: str) -> Any: ...
    def __contains__(self, item: str) -> bool: ...
    # 关于set, 与del
    # 必须显式申明生命周期

class _Context[_has_item]:
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
        """
        Example:
            if "user" in ctx
        :param item: keys to check
        :return: bool
        """
        return item in self.long or item in self.short

    def refresh(self):
        self.short.clear()

    async def close(self):
        for n, o in self.long.items():
            if not hasattr(o, "close"):
                continue
            try:
                await Async(o.close)()
            except (OSError, IOError, BrokenPipeError, ConnectionResetError) as e:
                warn(f"在释放 {n} 错误: {e}")

        self.long.clear()
