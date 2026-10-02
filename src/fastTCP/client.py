from .provider import Supplier
from .route import Blueprint
from .context import _Context
from .socket_ import _Socket
from .handler import process_msg, log
import asyncio
import logging

logger = logging.getLogger(__name__)

def _get_context_by_client(
        __socket__: "ClientFastTCP" # __socket__已经存在在上下文中, ClientFastTCP仅表明类型
):
    return __socket__.context

class ClientFastTCP(Blueprint, _Socket):
    def __init__(
            self,
            host: str = "127.0.0.1",
            port: int = 8080,
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.supplier = Supplier.default()
        self.context = _Context(__supplier__=self.supplier)

    def provide(self, sell: type | str):
        return self.supplier.provide(sell)

    async def connect(self):
        _Socket.__init__(self, *(await asyncio.open_connection(self.host, self.port)))

        self.context.long["__socket__"] = self

        self.supplier.provide("__context__")(_get_context_by_client)
        # 不直接将上下文存在上下文是因为当清理上下文会嵌套close, 而且会嵌套字典

        asyncio.create_task(self._recv_loop())

        logger.info(f"连接到 {self.address}")

    async def _recv_loop(self):
        while not self.writer.is_closing():
            await process_msg(self, self.context, self, logger)