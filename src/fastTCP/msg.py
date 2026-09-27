from dataclasses import dataclass

@dataclass
class RequestMessage:
    cmd: str
    body: bytes

@dataclass
class ResponseMessage:
    status_code : int
    body: bytes

class _UnificationMessage:
    def __init__(self, message_: ResponseMessage | RequestMessage):
        self.header = (message_.cmd if isinstance(message_, RequestMessage) else str(message_.status_code)).encode()
        self.body = message_.body
