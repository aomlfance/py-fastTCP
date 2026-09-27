from typing import Any, Callable
import inspect
import asyncio

class Async:
    def __init__(self, func: Callable):
        """
        将函数包装为异步
        :param func: 原函数
        """
        self.func = func
        self._sig = None

    @property
    def __signature__(self):
        if self._sig is None:
            self._sig = inspect.signature(self.func)
            return self._sig
        else:
            return self._sig

    async def __call__(self, *args, **kwargs):
        if inspect.iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        else:
            return await asyncio.to_thread(self.func, *args, **kwargs)

class _CannotClose:
    def __init__(self, obj: object):
        self.obj = obj

    def __getattribute__(self, name: str, /) -> Any:
        if name == "close":
            return lambda : None
        else:
            return getattr(super().__getattribute__("obj"), name)

def cannot_close(obj: object):
    return _CannotClose(obj)

def name(obj: Any) -> str:
    return obj.__name__ if hasattr(obj, "__name__") else str(obj)

def short_name(obj: Any):
    return repr(obj) if len(repr(obj)) < 12 else repr(obj)[:12]
