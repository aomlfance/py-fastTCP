"""
fastCTP继用了HTTP状态码, 来表达服务器的响应状态
"""
from typing import Any, NoReturn
from .socket_ import ResponseMessage
from .http_status import HTTP_STATUS
from .exceptions import Abort
import logging
import msgpack

class NoneResponse:
    def __bool__(self):
        return False

logger = logging.getLogger(__name__)

def make_response(
        res,
        default_status_code: int = 200,
) -> ResponseMessage:
    """
    用来将路由函数传来的值转为ResponsePayload
    """
    if isinstance(res, ResponseMessage):
        return res

    if not isinstance(res, tuple):
        res: tuple[Any] = (res, )
    elif len(res) < 1:
        raise TypeError("参数错误 应该有返回值")

    body = msgpack.packb(res[0])
    status_code = res[1] if len(res) > 1 else default_status_code

    return ResponseMessage(status_code=status_code, body=body)

def default_response(code: int, msg: str | None = None):
    if code not in HTTP_STATUS:
        logger.warning(f"{code} 是一个非HTTP标准响应码")
        return make_response((msg, code))
    else:
        return make_response((HTTP_STATUS[code]["meaning"] if msg is None else msg, code))

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