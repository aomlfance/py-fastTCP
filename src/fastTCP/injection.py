from typing import get_origin, get_args, Union, TYPE_CHECKING
import pydantic

if TYPE_CHECKING:
    from .route import Route

import inspect
from types import NoneType, UnionType
from .socket_ import  Socket
from .context import Context
from .utils import name
import logging

logger = logging.getLogger(__name__)

def injection(ctx: Context, route: Route):
    """
    根据路由函数的签名, 选择要注入的参数
    :raise TypeError, pydantic.ValidationError:
    """
    kwargs = {}

    for index, param in enumerate(inspect.signature(route).parameters.values()):
        # Socket, Context的优先级最高, 不允许注入
        if param.annotation == Socket:
            kwargs[param.name] = ctx["socket"]
            continue
        elif param.annotation == Context:
            kwargs[param.name] = ctx
            continue

        # 注入
        if param.name in ctx:
            value = ctx[param.name]
        # 绑定
        elif isinstance(param.annotation, type) and issubclass(param.annotation, pydantic.BaseModel):
            try:
                value = param.annotation(**ctx["payload"].body)
            except pydantic.ValidationError:
                raise
        # 否则优先取默认值
        elif param.default != param.empty:
            value = param.default
        # 否则是否允许NoneType
        elif get_origin(param.annotation) in (UnionType, Union) and NoneType in get_args(param.annotation):
            value = None
        else:
            raise TypeError(f"{name(route.handler)} 缺少参数{param.name}")

        kwargs[param.name] = value

    return kwargs