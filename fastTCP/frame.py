from .socket import Socket
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

async def run_route(route: Route, ctx:Context):
    """区分异步同步运行"""
    try:
        try:
            injection_kwargs = injection(ctx, route)
        except TypeError as e:
            logger.error(f"{type(e)} - {e}")
            return default_response(500)

        if inspect.iscoroutinefunction(route.handler):
            return await route.handler(ctx, **injection_kwargs)
        else:
            return route.handler(ctx, **injection_kwargs)
    except Abort as e:
        return e.response
    except ExitSignal:
        raise
    except Exception as e:
        logger.error(f"{type(e)} - {e}")
        return default_response(500)

class FastTCP(Blueprint):
    host: str = "127.0.0.1"
    port: int = 8964

    def __init__(self):
        super().__init__()
        self.server = asyncio.start_server(self.handle_client, self.host, self.port)
        self.clients = {}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        aom_socket = Socket(reader, writer)

        logger.info(f"客户端接入 - {aom_socket.address}")

        try:
            while True:
                await self.main_handler(aom_socket)
        except ExitSignal as e:
            logger.info(f"客户端退出 - {e}")
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.info(f"客户端退出 - {e}")
        finally:
            await aom_socket.close()

    async def main_handler(self, aom_socket: Socket):
        request_payload = await aom_socket.get_payload(RequestPayload)

        context = Context(aom_socket, request_payload)
        chain = self.get_chain(request_payload.cmd)

       # 这里留下一个trea_down预留代码
        for before_route in chain.before:
            res = await run_route(before_route, context)

            if res: break
        else:
            res = await run_route(chain.main_route, context)

            if not res:
                logger.warning(f"{request_payload.cmd}主路由没有返回响应")
                res = default_response(204)

        res = make_response(res)

        for after_route in chain.after:
            res = await run_route(after_route, context)

            if not isinstance(res, ResponsePayload):
                logger.warning("after 路由应该也返回 ResponsePayload")
                res = default_response(500)
                break

        await aom_socket.send_payload(res)

    async def start(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(lineno)d - %(levelname)s - %(message)s"
        )
        server = await self.server

        async with server:
            await server.serve_forever()