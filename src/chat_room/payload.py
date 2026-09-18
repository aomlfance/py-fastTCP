import pydantic


class User(pydantic.BaseModel):
    name: str

class MessagePayload(pydantic.BaseModel):
    text: str

class PushMessagePayload(pydantic.BaseModel):
    user_name: str
    text: str