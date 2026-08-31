from typing import Any, overload, NoReturn, ParamSpec
from .payload import ResponsePayload
from .exceptions import Abort

def make_response(
        res: tuple[Any, int] | ResponsePayload | tuple[Any] | Any,
):
    if isinstance(res, ResponsePayload):
        return res

    if not isinstance(res, tuple):
        res: tuple[Any] = (res, )

    elif len(res) < 1:
        raise TypeError("参数错误 应该有返回值")

    body = res[0] if isinstance(res[0], dict) else {"data": res[0]}

    status_code = res[1] if len(res) > 1 else 200

    return ResponsePayload(status_code=status_code, body=body)

STATUS_LIST = {
    400: "无法理解客户端的语法",
    401: "鉴权失败",
    ...: ""
}

def default_response(code):
    ...

def abort(code: int | ResponsePayload) -> NoReturn:
    if isinstance(code, int):
        raise Abort(
            ResponsePayload(
                status_code=code, body={"data": STATUS_LIST.get(code, "")}
            )
        )
    else:
        raise Abort(code)