from typing import Callable
import pydantic
from .chain import Chain
from .socket_ import Socket
from .exceptions import ExitSignal, Abort
from .payload import RequestPayload, ResponsePayload
from .response import default_response, make_response
from .context import Context
from .injection import injection
import inspect
import asyncio
import logging
from .route import Blueprint, Route

logger = logging.getLogger(__name__)

async def run_func(func: Callable, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)

async def run_route(route: Route, ctx:Context):
    """区分异步同步运行"""
    try:
        try:
            injection_kwargs = injection(ctx, route)
        except TypeError as e:
            logger.error(f"{type(e)} - {e}")
            return default_response(500)
        except pydantic.ValidationError as e:
            return default_response(400)

        return await run_func(route.handler, **injection_kwargs)
    except Abort as e:
        return e.response
    except ExitSignal:
        raise
    except Exception as e:
        logger.error(f"{type(e)} - {e}")
        return default_response(500)


async def run_chain(context: Context, chain: Chain) -> ResponsePayload:
    context.store.update(chain.param)

    for before_route in chain.before:
        res = await run_route(before_route, context)

        if res: break
    else:
        res = await run_route(chain.main_route, context)

        if res is None:
            logger.warning(f"{context.payload.cmd}主路由没有返回响应")
            res = default_response(204)

    res = make_response(res)
    last_res = res

    for after_route in chain.after:
        context["response"] = res
        res = await run_route(after_route, context)

        if res is None:
            res = last_res

    return res


class FastTCP(Blueprint):
    def __init__(
            self,
            host: str = "127.0.0.1",
            port: int = 8080,
            timeout: int | float = float("inf"),
    ):
        self.host = host
        self.port = port
        super().__init__()
        self.server = asyncio.start_server(self.handle_client, self.host, self.port)
        self.clients = {}
        self.disconnect_handler: Callable | None = None
        self.disconnect_handler_inj: bool = False
        self.timeout = timeout

    def on_disconnect(self, func):
        if self.disconnect_handler is not None:
            print()

        self.disconnect_handler = func

        parameters = inspect.signature(func).parameters

        if len(parameters) != 0:
            self.disconnect_handler_inj = True
        return func

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        socket: Socket = Socket(reader, writer, timeout=self.timeout)
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
                args = ()
                if self.disconnect_handler_inj:
                    args = (socket, )
                await run_func(self.disconnect_handler, *args)

    async def main_handler(self, socket: Socket):
        request_payload = await socket.get_payload(RequestPayload)

        context = Context(socket, request_payload)

        try:
            res = await run_chain(context, self.get_chain(context.payload.cmd))
        except:
            raise
        else:
            await socket.send_payload(res)
            logger.info(f"{request_payload.cmd} - {res.status_code}")

    async def start(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(lineno)d - %(levelname)s - %(message)s"
        )
        server = await self.server

        async with server:
            await server.serve_forever()