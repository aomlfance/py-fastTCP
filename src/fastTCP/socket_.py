import asyncio
import json
import struct
import pydantic

from .request_dq import RequestDequeManager
from typing import TypeVar, Any, TYPE_CHECKING, Protocol, Callable
from types import SimpleNamespace
from .payload import RequestPayload, ResponsePayload
from .request import make_requests
from .exceptions import ExitSignal
from dataclasses import dataclass
import io

B = TypeVar("B", bound=pydantic.BaseModel)

DEF_MAX_BODY_SIZE = 1 * 1024 * 1024

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

class Socket(Protocol):
    """实际向外开放的类"""
    # 实际接收由路由处理
    async def request(self, cmd: str , body: Any) -> RequestPayload: ...

class BaseSocket:
    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            timeout: int | float = float('inf'),
            buffer_size: int = 1024 * 1024 * 128
    ):
        self.reader = reader
        self.writer = writer

        self.timeout = timeout
        self.buffer_size = buffer_size

        self.address = self.writer.get_extra_info('peername')

    async def read(self, size: int, timeout: int | float | None = None):
        if timeout is None:
            timeout = self.timeout

        try:
            chunk = await asyncio.wait_for(
                self.reader.read(size),
                timeout
            )
        except asyncio.TimeoutError:
            raise ExitSignal("超时")

        if not chunk:
            raise ExitSignal("客户端退出")
        else:
            return chunk

    async def read_until(self, size: int, timeout: int | float | None = None, buffer_size: int | None = None):
        if buffer_size is None:
            buffer_size = self.buffer_size

        surplus_size = size
        bytes_io = io.BytesIO()

        while surplus_size > 0:
            chunk = await self.read(
                surplus_size if surplus_size < buffer_size else buffer_size,
                timeout
            )
            surplus_size -= len(chunk)
            bytes_io.write(chunk)

        return bytes_io.getvalue()

    def write(self, bytes_: bytes):
        self.writer.write(bytes_)

    async def drain(self):
        await self.writer.drain()

    async def write_and_drain(self, bytes_: bytes):
        self.write(bytes_)
        await self.drain()

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

class _Socket(BaseSocket):

    """封装r, w提供api功能"""
    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            timeout: int | float = float("inf"),
            buffer_size: int = 1024 * 1024
    ):
        self.req_dq_mg = RequestDequeManager()
        super().__init__(reader, writer, timeout, buffer_size)

    async def receive(self) -> RequestMessage:
        while True:
            before_header_bytes = await self.read_until(2)

            number = struct.unpack("!h", before_header_bytes)[0]

            msg_type = None

            if number != 0: #  = 0 -> push
                if number < 0:
                    msg_type = "response"
                else:
                    msg_type = "request"

                header_size = abs(number)

                header = await self.read_until(header_size)

                try:
                    header_string = header.decode()
                except UnicodeDecodeError:
                    raise ExitSignal("编码失败")

                if msg_type == "response":
                    try:
                        status_code = int(header_string)
                    except ValueError:
                        raise ExitSignal("状态码应该为int")
                else:
                    cmd = header_string
            else:
                raise ExitSignal("现在不支持呢")

            body_size = struct.unpack("!I", await self.read_until(4))[0]

            body = await self.read_until(body_size)

            if msg_type == "response":
                if self.req_dq_mg.can_dequeue():
                    self.req_dq_mg.dequeue(ResponseMessage(status_code, body))
                continue
            else:
                return RequestMessage(cmd, body)

    async def _send_message(self, message: ResponseMessage | RequestMessage):
        k = 1 if isinstance(message, RequestMessage) else -1
        message = _UnificationMessage(message)

        await self.write_and_drain(
            struct.pack("!h", k * len(message.header)) +
            message.header +
            struct.pack("!I", len(message.body)) +
            message.body
        )

    async def response(self, response_message: ResponseMessage):
        await self._send_message(response_message)

    async def request(self, request_message: RequestMessage) -> ResponseMessage:
        await self._send_message(request_message)
        return await self.req_dq_mg.enqueue()
