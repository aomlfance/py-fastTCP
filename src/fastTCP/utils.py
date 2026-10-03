from typing import Any, Callable, Literal
import inspect
import asyncio
from warnings import warn

def name(obj: Any) -> str:
    return obj.__name__ if hasattr(obj, "__name__") else str(obj)

def short_name(obj: Any):
    return repr(obj) if len(repr(obj)) < 12 else repr(obj)[:12]

async def _clear(obj: dict):
    for n, o in obj.items():
        if hasattr(o, "aclose") and callable(o.aclose):
            handler = o.alose
        elif hasattr(o, "close") and callable(o.close):
            handler = Async(o.close, "clogging")
        else:
            continue
        try:
            await handler()
        except (OSError, IOError, BrokenPipeError, ConnectionResetError) as e:
            warn(f"在释放 {n} 错误: {e}")

    obj.clear()

class TempSignature:
    """支持缓存签名"""
    def __init__(self, handler: Callable):
        self.handler = self.__wrapped__ = handler
        self._sig = None

    @property
    def __signature__(self):
        if self._sig is None:
            self._sig = inspect.signature(self.handler)
        return self._sig

    def __call__(self, *args, **kwargs):
        return self.handler(*args, **kwargs)

class Async:
    def __init__(self, handler: Callable, way: Literal["clogging", "thread_pool"]="thread_pool"):
        """
        将函数包装为异步
        :param handler: 原函数
        """
        self.handler = handler
        self.way = way

    @property
    def __signature__(self):
        return inspect.signature(self.handler)

    async def __call__(self, *args, **kwargs):
        if inspect.iscoroutinefunction(inspect.unwrap(self.handler)):
            return await self.handler(*args, **kwargs)
        else:
            if self.way == "thread_pool":
                return await asyncio.to_thread(self.handler, *args, **kwargs)
            else:
                return self.handler(*args, **kwargs)
