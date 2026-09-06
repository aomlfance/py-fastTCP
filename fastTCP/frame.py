import pydantic
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
        elif inspect.isgeneratorfunction(route.handler):
            times = 0
            gen = route.handler(**injection_kwargs)
            # 这里想要达成的效果是区分yield, return
            with contextlib.closing(gen):
                while True:
                    if times >= 128:
                        logger.error("已经迭代了太多次了")
                        return default_response(408)
                    try:
                        res = next(gen)
                    except StopIteration as e:
                        if e.value is None:
                            logger.error("根据生成器路由规范, 要明确结束对话应该使用return而不是自然耗尽.")
                            return None

                        return e.value
                    else:
                        if res is None:
                            logger.warning("yield应该返回明确的值!")
                            res = default_response(100)

                        await ctx.socket.send_payload(make_response(res, 100))
                    finally:
                        times += 1
        else:
            return route.handler(**injection_kwargs)
    except Abort as e:
        return e.response
    except ExitSignal:
        raise
    except Exception as e:
        logger.error(f"{type(e)} - {e}")
        return default_response(500)

class FastTCP(Blueprint):
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        super().__init__()
        self.server = asyncio.start_server(self.handle_client, self.host, self.port)
        self.clients = {}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        aom_socket = Socket(reader, writer)
        self.clients[aom_socket.address] = aom_socket

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
            self.clients.pop(aom_socket.address, None)

    async def main_handler(self, aom_socket: Socket):
        request_payload = await aom_socket.get_payload(RequestPayload)

        context = Context(aom_socket, request_payload)
        chain = self.get_chain(request_payload.cmd)
        context.store.update(chain.param)

        try:
            for before_route in chain.before:
                res = await run_route(before_route, context)

                if res: break
            else:
                res = await run_route(chain.main_route, context)

                if res is None:
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
        except:
            raise
        else:
            logger.info(f"{request_payload.cmd} - {res.status_code}")


    async def start(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(lineno)d - %(levelname)s - %(message)s"
        )
        server = await self.server

        async with server:
            await server.serve_forever()