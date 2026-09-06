import asyncio
import json
import struct
import pydantic
from typing import TypeVar, Any
from .exceptions import ExitSignal

B = TypeVar("B", bound=pydantic.BaseModel)

class Socket:
    """封装r, w提供api功能"""
    def __init__(self, orig_stream_reader: asyncio.StreamReader, orig_stream_writer: asyncio.StreamWriter):
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

    async def get_bytes_msg(self, max_size: int = 1024):
        """获得bytes"""
        size = await self.get_head_size()

        if size > max_size:
            raise ExitSignal(f"太大的大小 期盼应该不大于{max_size} 实际为{size}")

        residual_size = size
        body = b""

        while residual_size > 0:
            chunk = await self.get_chunk(residual_size)
            body += chunk
            residual_size -= len(chunk)

        return body

    async def get_str_msg(self, max_size: int = 1024, encoding: str="utf-8"):
        """获得str数据"""
        return (await self.get_bytes_msg(max_size)).decode(encoding)

    async def get_json_msg(self, max_size: int = 1024):
        """获得json数据"""
        try:
            return json.loads(await self.get_bytes_msg(max_size))
        except json.JSONDecodeError as e:
            raise ExitSignal(f"解析json失败 - {e}")

    async def get_payload(self, base_model:type[B], max_size: int=1024) -> B:
        """获得结构体"""
        json_data = await self.get_json_msg(max_size)

        if not isinstance(json_data, dict):
            raise ExitSignal(f"客户端 {self.address} 发送了一个非dict的json数据")

        try:
            return base_model(**json_data)
        except pydantic.ValidationError as e:
            raise ExitSignal(f"解析payload错误 - {e}")

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