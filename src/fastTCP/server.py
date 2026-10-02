from typing import Callable
from .socket_ import _Socket
from .exceptions import ExitSignal
from .context import _Context
import inspect
import asyncio
import logging
from .route import Blueprint
from .utils import Async
from .provider import Supplier
from .handler import process_msg

logger = logging.getLogger(__name__)

def _get_get_context_by_server_func(server: "FastTCPServer"):
    def _get_context_by_server(__socket__: _Socket):
        return server.clients[__socket__.address]
    return _get_context_by_server

class FastTCPServer(Blueprint): # ReqDqMg
    def __init__(
            self,
            host: str = "127.0.0.1",
            port: int = 8080,
            timeout: int | float = float("inf"),
    ):
        self.host = host
        self.port = port
        self.supplier = Supplier.default()

        super().__init__()

        self.server_task = asyncio.start_server(self.handle_client, self.host, self.port)

        self.clients = {}

        self.disconnect_handler: Callable | None = None
        self.disconnect_handler_inj: bool = False

        self.provide("__context__")(_get_get_context_by_server_func(self))

        self.timeout = timeout

    def provide(self, sell: type | str):
        return self.supplier.provide(sell)

    def on_disconnect(self, func):
        self.disconnect_handler = func
        parameters = inspect.signature(func).parameters
        if len(parameters) != 0:
            self.disconnect_handler_inj = True
        return func

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        socket = _Socket(reader, writer, timeout=self.timeout)

        ctx = _Context(__socket__=socket, __supplier__=self.supplier)

        self.clients[socket.address] = ctx

        logger.info(f"客户端接入 - {socket.address}")

        try:
            while True:
                await process_msg(self, ctx, socket, logger)
        except (ExitSignal, ConnectionResetError, BrokenPipeError)  as e:
            logger.info(f"客户端退出 - {e}")

        await ctx.close()

        self.clients.pop(socket.address, None)

        if callable(self.disconnect_handler):

            if self.disconnect_handler_inj:
                args = (socket, )
            else:
                args = ()

            await Async(self.disconnect_handler)(*args)

    async def serve_forever(self):
        server = await self.server_task

        async with server:
            await server.serve_forever()