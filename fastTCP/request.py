from .payload import RequestPayload
import pydantic
from typing import Any

def make_requests(cmd: str, body: Any) -> RequestPayload:
    if isinstance(body, RequestPayload):
        return body

    if isinstance(body, pydantic.BaseModel):
        body = body.model_dump()
    elif not isinstance(body, dict):
        body = {"data": body}

    return RequestPayload(cmd=cmd, body=body)
