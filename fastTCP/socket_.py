import asyncio
import json
import struct
import pydantic
from typing import TypeVar, Any
from .request import make_requests
from .payload import ResponsePayload
from .exceptions import ExitSignal
import io

B = TypeVar("B", bound=pydantic.BaseModel)

class Socket:

    default_max_body_size = 1 * 1024 * 1024

    """封装r, w提供api功能"""
    def __init__(
            self,
            orig_stream_reader: asyncio.StreamReader,
            orig_stream_writer: asyncio.StreamWriter,

    ):
        self.stream_reader = orig_stream_reader
        self.stream_writer = orig_stream_writer
        self.address = self.stream_writer.get_extra_info('peername')

    async def get_chunk(self, size:int):
        """获得块"""
        if not (chunk := await self.stream_reader.read(size)):
            raise ExitSignal(f'客户端{self.address}退出连接')
        else:
            return chunk

    async def get_head_size(self) -> int:
        """获得头大小"""
        head = b""

        while len(head) < 4:
            head += await self.get_chunk(4 - len(head))

        size = struct.unpack("!I", head)[0]

        return size

    async def get_bytes_msg(self, max_size: int | None = None):
        """获得bytes"""
        size = await self.get_head_size()

        if max_size is None:
            max_size = self.default_max_body_size

        if size > max_size:
            raise ExitSignal(f"太大的大小 期盼应该不大于{max_size} 实际为{size}")

        buf = io.BytesIO()

        residual_size = size

        while residual_size > 0:
            chunk = await self.get_chunk(residual_size)
            buf.write(chunk)
            residual_size -= len(chunk)

        return buf.getvalue()

    async def get_str_msg(self, max_size: int | None = None, encoding: str = "utf-8"):
        """获得str数据"""
        return (await self.get_bytes_msg(max_size)).decode(encoding)

    async def get_json_msg(self, max_size: int | None = None):
        """获得json数据"""
        try:
            return json.loads(await self.get_bytes_msg(max_size))
        except json.JSONDecodeError as e:
            raise ExitSignal(f"解析json失败 - {e}")

    async def get_msgpack(self, max_size: int | None = None):
        ...

    async def get_payload(self, base_model: type[B] | list[type[B]], max_size: int | None = None) -> B:
        """
        :param base_model: 结构体对象, 可以为一个pydantic.BaseModel的基类, 或列表分割表示宽容多个结构体类型
        :param max_size: 允许的body最大字节大小
        :return: 由base_model决定, 返回其怒许结构体类型的实例
        """
        json_data = await self.get_json_msg(max_size)

        if not isinstance(json_data, dict):
            raise ExitSignal(f"客户端 {self.address} 发送了一个非dict的json数据")

        permit_of_rage_list = base_model if isinstance(base_model, list) else [base_model]

        lastest = len(permit_of_rage_list) - 1

        for i, b in enumerate(permit_of_rage_list):
            try:
                return b(**json_data)
            except pydantic.ValidationError as e:
                if i == lastest:
                    raise ExitSignal(f"解析payload错误 - {e}")
                else:
                    continue
        else:
            raise AssertionError("in get_payload()")

    async def send_bytes_msg(self, msg: bytes) -> None:
        """发送bytes"""
        msg_size = len(msg)

        head = struct.pack("!I", msg_size)

        self.stream_writer.write(head + msg)

        await self.stream_writer.drain()

    async def send_str_msg(self, msg: str, encoding: str="utf-8") -> None:
        """发送str"""
        msg_bytes = msg.encode(encoding= encoding)
        return await self.send_bytes_msg(msg_bytes)

    async def send_json_msg(self, msg: Any, encoding: str="utf-8") -> None:
        """发送json数据"""
        return await self.send_str_msg(json.dumps(msg, default=str), encoding= encoding)

    async def send_payload(self, msg: B, encoding: str="utf-8", **kwargs) -> None:
        """发送结构体"""
        await self.send_json_msg(msg.model_dump(**kwargs), encoding= encoding)

    async def request(self, cmd: str, body: Any):
        """该方法只适用服务端"""
        await self.send_payload(make_requests(cmd, body))
        return await self.get_payload(ResponsePayload)

    async def close(self):
        """关闭"""
        try:
            if self.stream_writer and not self.stream_writer.is_closing():
                self.stream_writer.close()
                await self.stream_writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"关闭连接时发生未知错误: {e}")