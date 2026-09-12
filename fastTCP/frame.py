import pydantic

from chain import Chain
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
import contextlib

logger = logging.getLogger(__name__)

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

        if inspect.iscoroutinefunction(route.handler):
            return await route.handler(**injection_kwargs)
        elif inspect.isasyncgenfunction(route.handler):
            logger.warning("当前版本不再允许生成器路由")
            return default_response(500)
        else:
            return route.handler(**injection_kwargs)
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

    for after_route in chain.after:
        res = make_response(await run_route(after_route, context))

    return res



class FastTCP(Blueprint):
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        super().__init__()
        self.server = asyncio.start_server(self.handle_client, self.host, self.port)
        self.clients = {}


    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        socket = Socket(reader, writer)
        self.clients[socket.address] = socket

        logger.info(f"客户端接入 - {socket.address}")

        try:
            while True:
                await self.main_handler(socket)
        except ExitSignal as e:
            logger.info(f"客户端退出 - {e}")
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.info(f"客户端退出 - {e}")
        finally:
            await socket.close()
            self.clients.pop(socket.address, None)

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