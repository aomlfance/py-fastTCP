import pydantic

class RequestPayload(pydantic.BaseModel):
    cmd: str
    body: dict

class ResponsePayload(pydantic.BaseModel):
    status_code: int
    body: dict
