from typing import Callable
from .chain import Chain
from .socket_ import _Socket
from .exceptions import ExitSignal
from .payload import RequestPayload, ResponsePayload
from .response import default_response, make_response
from .context import Context
from .request_dq import RequestDequeManager
import inspect
import asyncio
import logging
from .route import Blueprint
from .utils import Async

logger = logging.getLogger(__name__)

async def run_chain(context: Context, chain: Chain) -> ResponsePayload:
    context.store.update(chain.param)

    for before_route in chain.before:
        res = await before_route(context)

        if res is not None: break
    else:
        res = await chain.main_route(context)

        if res is None:
            logger.warning(f"{context.payload.cmd}主路由没有返回响应")
            res = default_response(204)

    res = make_response(res)
    last_res = res

    for after_route in chain.after:
        context["response"] = res
        res = await after_route(context)

        if res is None:
            res = last_res
        else:
            res = make_response(res)

    return res


class FastTCPServer(Blueprint): # ReqDqMg
    def __init__(
            self,
            host: str = "127.0.0.1",
            port: int = 8080,
            timeout: int | float = float("inf"),
    ):
        self.host = host
        self.port = port

        Blueprint.__init__(self)
        RequestDequeManager.__init__(self)

        self.server_task = asyncio.start_server(self.handle_client, self.host, self.port)

        self.clients = {}

        self.disconnect_handler: Callable | None = None
        self.disconnect_handler_inj: bool = False

        self.timeout = timeout

    def on_disconnect(self, func):
        self.disconnect_handler = func
        parameters = inspect.signature(func).parameters
        if len(parameters) != 0:
            self.disconnect_handler_inj = True
        return func

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        socket = _Socket(self, reader, writer, timeout=self.timeout)
        self.clients[socket.address] = socket

        logger.info(f"客户端接入 - {socket.address}")

        try:
            while True:
                await self.main_handler(socket)
        except (ExitSignal, ConnectionResetError, BrokenPipeError)  as e:
            logger.info(f"客户端退出 - {e}")
        finally:
            await socket.close()

            self.clients.pop(socket.address, None)

            if callable(self.disconnect_handler):

                if self.disconnect_handler_inj:
                    args = (socket, )
                else:
                    args = ()

                await Async(self.disconnect_handler)(*args)

    async def main_handler(self, socket: _Socket):
        payload = await socket.get_payload([RequestPayload, ResponsePayload])

        if isinstance(payload, ResponsePayload):
            if self.can_dequeue():
                self.dequeue(payload)
            return

        context = Context(socket, payload)

        try:
            res = await run_chain(context, self.get_chain(context.payload.cmd))
        except:
            raise
        else:
            await socket.send_payload(res)
            logger.info(f"{payload.cmd} - {res.status_code}")

    async def serve_forever(self):
        server = await self.server_task

        async with server:
            await server.serve_forever()

    def suspend(self):
        task = asyncio.create_task(self.serve_forever())
        return task