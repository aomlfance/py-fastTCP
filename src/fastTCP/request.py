import pydantic
from typing import Any
from .msg import RequestMessage
import msgpack

def make_requests(cmd: str, body: Any):
    if isinstance(body, pydantic.BaseModel):
        body = body.model_dump()
    if isinstance(body, str | int | float | bytes | dict | tuple | list):
        return RequestMessage(cmd, msgpack.packb(body))
    else:
        raise TypeError("不支持的类型")