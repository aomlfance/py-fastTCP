from .context import Context
from .route import Route
from typing import get_origin, get_args, Literal, Union
from types import NoneType, UnionType
from .utils import short_name, name
import logging

logger = logging.getLogger(__name__)

def injection(ctx: Context, route: Route):
    """
    根据路由函数的签名, 选择要注入的参数
    :raise TypeError
    """
    kwargs = {}

    for index, param in enumerate(route.handler_sig.parameters.values()):
        # 跳过第一位上下文
        if index == 0:
            continue

        if param.name in ctx.store:
            value = ctx[param.name]
            origin = get_origin(param.annotation)

            # 检查是否与类型提示一致
            if (
                origin is None and param.annotation != param.empty
                and not issubclass(type(value), param.annotation)
            ):
                raise TypeError(f"{param.name} 要求的{param.annotation}与{short_name(value)}的{type(value)}不符合", 500)
            elif origin is Literal and value not in get_args(param.annotation):
                raise TypeError(f"{short_name(value)} 与 {param.name}期待的{get_args(param.annotation)}不同")
            else:
                logger.debug(f"{param.annotation} 暂时不支持的类型提示")
        # 优先取默认值
        elif param.default != param.empty:
            value = param.default
        # 否则是否允许NoneType
        elif get_origin(param.annotation) in (UnionType, Union) and NoneType in get_args(param.annotation):
            value = None
        else:
            raise TypeError(f"{name(route.handler)} 缺少参数{param.name}")

        kwargs[param.name] = value

    return kwargs