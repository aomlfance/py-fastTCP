"""
fastCTP继用了HTTP状态码, 来表达服务器的响应状态
"""
from typing import Any, NoReturn
from .payload import ResponsePayload
from .http_status import HTTP_STATUS
from .exceptions import Abort
import logging

logger = logging.Logger(__name__)

def make_response(
        res: tuple[Any, int] | ResponsePayload | tuple[Any] | Any,
):
    """
    用来将路由函数传来的值转为ResponsePayload
    """
    if isinstance(res, ResponsePayload):
        return res

    if not isinstance(res, tuple):
        res: tuple[Any] = (res, )
    elif len(res) < 1:
        raise TypeError("参数错误 应该有返回值")

    body = res[0] if isinstance(res[0], dict) else {"data": res[0]}
    status_code = res[1] if len(res) > 1 else 200

    return ResponsePayload(status_code=status_code, body=body)

def default_response(code: int, msg: str | None = None):
    if code not in HTTP_STATUS:
        logger.warning(f"{code} 是一个非HTTP标准响应码")
        return ResponsePayload(status_code=code, body=({} if msg is None else {"msg": msg}) )
    else:
        return ResponsePayload(status_code=code, body=({"msg": HTTP_STATUS[code]["meaning"]} if msg is None else {"msg": msg}) )

# 为了不混淆歧义, abort 分为了 code 与 ResponsePayload
def abort_code(code: int, msg: str | None = None) -> NoReturn:
    raise Abort(default_response(code, msg))

def abort_args(*args) -> NoReturn:
    """像在返回响应短路"""
    # 在函数中 return arg1, arg2
    # 外部获得是一个元组对象(arg1, arg2)
    # 我们希望不要在 raise Abort(make_response())中再套一个元组
    # 所有提供此接口
    raise Abort(make_response(args))

def abort_res(res: ResponsePayload) -> NoReturn:
    raise Abort(res)