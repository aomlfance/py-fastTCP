from typing import Any

from .context import _Context
from .msg import ResponseMessage
from .socket_ import _Socket
from .exceptions import ExitSignal
from .handler import process_msg
from .route import Blueprint
from .provider import Supplier
from .utils import _clear

import asyncio
import logging

logger = logging.getLogger(__name__)

async def _main_loop(bp: Blueprint, ctx: _Context, socket: _Socket, supplier: Supplier):
    try:
        while not socket.writer.is_closing():
            await process_msg(bp, ctx, socket, logger, supplier)
    except (ExitSignal, ConnectionResetError, BrokenPipeError) as e:
        logger.info("服务器退出")

class Maintenance(Blueprint):
    # 在这里需要理解socket的本质
    # 这里论述一下, 因为以下要统一, 并且server client也是有一个共同的基
    # server占一个socket用来接受连接, 再把该连接剥离为一个socket即(>2). 不过内核中我们维护connection(管道的语义)
    # client是直接占一个fd来连接, 不用剥离(也可以说已经剥离了)
    # server与client都只是基于socket再吧了吧里的
    def __init__(self):
        super().__init__()

        self.conns: dict[tuple, _Context] = {}
        self.supplier = Supplier.default()

    def provide(self, *args, **kwargs):
        return self.supplier.provide(*args, **kwargs)

    @property
    def _unique_client(self) -> _Context:
        if len(self.conns) != 1:
            raise RuntimeError("连接不唯一")
        else:
            return next(iter(self.conns.values()))

    async def request(self, *args, **kwargs) -> ResponseMessage:
        return await self._unique_client["__socket__"].request(*args, **kwargs)

    async def _main_handler(self, ctx: _Context, socket: _Socket):
        await _main_loop(self, ctx, socket, self.supplier)
        await self._uninstall_conn(socket)

    async def _handle_client(self, r: asyncio.StreamReader, w: asyncio.StreamWriter):
        await self._main_handler(*self._add_conn(r, w))

    async def serve_forever(self, *args, **kwargs):
        """
        监听主循环.

        Args:
            *args:
            **kwargs:

        Returns:

        """
        async with (server := await asyncio.start_server(self._handle_client, *args, **kwargs)):
            await server.serve_forever()

    def _add_conn(self, r: asyncio.StreamReader, w: asyncio.StreamWriter, *args, **kwargs) -> tuple[_Context, _Socket]:
        """
        添加一个连接.

        把asyncio库返回的裸writer与reader, 封装为_Socket, 提供类socket的API, 并封装receive...等方法

        并存入连接表, 创建连接上下文.

        Args:
            r: 原reader
            w: 原writer
            *args: 要传给_Socket.__init__的参数
            **kwargs: 同*args

        Returns:
            返回一个tuple, [0] 为上下文(附自己与socket), [1] 为以及封装好的socket
        """
        socket = _Socket(r, w, *args, **kwargs)

        ctx = _Context.take_self(__socket__=socket)

        self.conns[socket.address] = ctx

        return ctx, socket

    async def _uninstall_conn(self, o : _Socket):
        await o.aclose()

        self.conns.pop(o.address, None)

        ...

    async def connect(self, *args, timeout: int | float | None = None, **kwargs):
        """
        连接到服务器

        Args:
            timeout: 接收超时的时间
            *args: 继承至asyncio.open_connection的签名
            **kwargs: 继承至asyncio.open_connection的签名

        Returns:
            返回一个在后台反复监听以路由与唤醒request的协程
        """
        r, w = await asyncio.open_connection(*args, **kwargs)

        ctx, socket = self._add_conn(
            r, w, timeout=timeout
        )

        task = asyncio.create_task(self._main_handler(ctx, socket))

        return task

    async def aclose(self):
        """
        清理所有连接上下文并如果存储的值有 close | aclose 方法会自动调用
        """
        await _clear(self.conns)
