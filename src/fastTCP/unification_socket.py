from typing import Any, Callable, TypeVar
from .context import _Context
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

_OF = TypeVar("_OF", bound=Callable)

class FastTCP(Blueprint):
    # 在这里需要理解socket的本质
    # 这里论述一下, 因为以下要统一, 并且server client也是有一个共同的基
    # server占一个socket用来接受连接, 再把该连接剥离为一个socket即(>2). 不过内核中我们维护connection(管道的语义)
    # client是直接占一个fd来连接, 不用剥离(也可以说已经剥离了)
    # server与client都只是基于socket再吧了吧里的
    def __init__(self):
        super().__init__()

        self.conns: dict[tuple, _Context] = {}
        self.supplier = Supplier.default()

    def provide(self, sell: Any) -> Callable[[_OF], _OF]:
        return self.supplier.provide(sell)

    def match(self, judgment_thing: Callable) -> Callable[[_OF], _OF]:
        return self.supplier.match(judgment_thing)

    @property
    def _unique_client(self) -> _Socket:
        """
        唯一的连接(绝大多场景都指client端)

        Returns:
            连接表中的唯一的_Socket

        Raises:
            RuntimeError: 连接不唯一时
            KeyError: 连接上下文没存原_Socket(预期内总不发生)
        """
        if len(self.conns) != 1:
            raise RuntimeError("连接不唯一")
        else:
            return next(iter(self.conns.values()))["__socket__"]

    @property
    def address(self):
        """
        唯一对端的地址(语境见self._unique_client)
        """
        # 为满足Socket协议
        return self._unique_client.address

    async def request(self, *args, **kwargs) -> tuple[int, Any]:
        """
        向唯一对端请求(语境见self._unique_client)
        """
        return await self._unique_client.request(*args, **kwargs)

    async def _main_handler(self, ctx: _Context, socket: _Socket):
        """
        主要的处理连接的函数.

        处理一个连接的生命周期(除了连接).与其期间发生的事件.

        Args:
            ctx: 因为socket把生命周期寄托在了_Context, 为了管理其生命周期, 需要是必定的
            socket: 关于为什么要显式传入_Context, 见_Context注释.

        """
        await _main_loop(self, ctx, socket, self.supplier)
        await self._uninstall_conn(socket)

    async def _handle_client(self, r: asyncio.StreamReader, w: asyncio.StreamWriter):
        """
        处理连接.

        这是接收连接后的第一个入口.会把r, w封装_Socket并存入连接上下文记录在self.conns.

        最后开始循环接收响应 -> requestDp | 请求 -> 路由.
        """
        await self._main_handler(*self._add_conn(r, w))

    async def serve_forever(self, *args, **kwargs):
        """
        监听主循环.

        Args:
            *args: 继承asyncio.start_server()的签名
            **kwargs: 同上
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
        """
        卸载连接.

        Args:
            o: 原_Socket.为保证语义,这不用被寄托的_Context.而是通过o.address反查

        """
        ctx = self.conns.pop(o.address)

        await ctx.aclose()

        ... # 保留on_disconnect

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
        异步关闭.

        清理所有连接上下文并如果存储的值有 close | aclose 方法会自动调用
        """
        await _clear(self.conns)
