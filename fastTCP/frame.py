import asyncio
from types import UnionType, NoneType
from typing import get_args, get_origin, Union, Literal, Any
from .socket import AomSocket
from .exceptions import ExitSignal, Abort
from .payload import RequestPayload
from .response import make_response, abort
from .context import Context
import inspect
import logging
from .route import Blueprint, Route, name

logger = logging.getLogger(__name__)

def short_name(obj: Any):
    return str(obj) if len(str(obj)) < 12 else str(obj)[:12]

async def run_with_error(func, *args, **kwargs):
    """区分异步同步运行"""
    try:
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    except Abort as e:
        return e.response
    except ExitSignal:
        raise
    except Exception as e:
        logger.error(f"{e}")
        try:
            abort(500)
        except Abort as e:
            return e.response

def injection(ctx: Context, route: Route):
    """
    根据路由函数的签名, 选择要注入的参数
    :raise TypeError
    """
    kwargs = {}

    for index, param in enumerate(route.handler_sig.parameters.values()):
        # 跳过第一位上下文
        if index == 0:
            continue

        if param.name in ctx.store:
            value = ctx[param.name]
            origin = get_origin(param.annotation)

            # 检查是否与类型提示一致
            if (
                origin is None and param.annotation != param.empty
                and not isinstance(param.annotation, type(value))
            ):
                raise TypeError(f"{param.name} 要求的{param.annotation}与{short_name(value)}的{type(value)}不符合", 500)
            elif origin is Literal and value not in get_args(param.annotation):
                raise TypeError(f"{short_name(value)} 与 {param.name}期待的{get_args(param.annotation)}不同")
            else:
                logger.debug(f"{param.annotation} 暂时不支持的类型提示")
        # 优先取默认值
        elif param.default != param.empty:
            value = param.default
        # 否则是否允许NoneType
        elif get_origin(param.annotation) in (UnionType, Union) and NoneType in get_args(param.annotation):
            value = None
        else:
            raise TypeError(f"{name(route.handler)} 缺少参数{param.name}")

        kwargs[param.name] = value

    return kwargs

class FastTCP(Blueprint):
    host: str = "127.0.0.1"
    port: int = 8964

    def __init__(self):
        super().__init__()
        self.server = asyncio.start_server(self.handle_client, self.host, self.port)
        self.clients = {}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        aom_socket = AomSocket(reader, writer)

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

    async def main_handler(self, aom_socket: AomSocket):
        request_payload = await aom_socket.get_payload(RequestPayload)

        context = Context(aom_socket, request_payload)
        chain = self.get_chain(request_payload.cmd)

        for route in [*chain.before, chain.main_route]:
            try:
                kwargs = injection(context, route)
            except TypeError as e:
                logger.error(f"{e}")
                try:
                    abort(500)
                except Abort as e:
                    res = e.response
            else:
                res = await run_with_error(route.handler, context, **kwargs)

            if res is not None:
                break

        for route in chain.after:
            res = await run_with_error(route.handler, context)

        if res is None:
            res = "", 204

        res_payload = make_response(res)
        await context.aom_socket.send_payload(res_payload)

    async def start(self):
        server = await self.server

        async with server:
            await server.serve_forever()