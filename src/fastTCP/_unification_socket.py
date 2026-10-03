from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        self.supplier = Supplier()

    def provide(self, *args, **kwargs):
        return self.supplier.provide(*args, **kwargs)

    @property
    def _unique_client(self) -> _Context:
        if len(self.conns) != 1:
            raise RuntimeError("连接不唯一")
        else:
            return next(iter(self.conns.values()))

    def request(self, *args, **kwargs) -> ResponseMessage:
        return self._unique_client.socket.request(*args, *kwargs)

    async def _main_handler(self, ctx: _Context, socket: _Socket):
        await _main_loop(self, ctx, socket, self.supplier)
        await self._uninstall_conn(socket)

    async def _handle_client(self, r: asyncio.StreamReader, w: asyncio.StreamWriter):
        await self._main_handler(*self._add_a_conn(r, w))

    async def serve_forever(self, *args, **kwargs):
        async with (server := await asyncio.start_server(self._handle_client, *args, **kwargs)):
            await server.serve_forever()

    def _add_a_conn(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> tuple[_Context, _Socket]:
        socket = _Socket(r, w)

        ctx = _Context(__socket__=socket)

        self.conns[socket.address] = ctx

        return ctx, socket

    async def _uninstall_conn(self, o : _Socket | _Context):
        await (o if isinstance(o, _Socket) else o.socket).close()

        self.conns.pop(o.address, None)

        ...

    async def connect(self, *args, **kwargs):
        ctx, socket = self._add_a_conn(
            *(await asyncio.open_connection(*args, **kwargs))
        )

        task = asyncio.create_task(self._main_handler(ctx, socket))

        return task

    async def async_close(self):
        await _clear(self.conns)

    def close(self):
        asyncio.run(self.async_close())