from typing import Any

from .provider import Supplier
from .route import Blueprint
from .context import _Context
from .socket_ import _Socket
import asyncio
import logging

logger = logging.getLogger(__name__)

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

        asyncio.create_task(self._recv_loop())

        logger.info(f"连接到 {self.address}")

    async def _recv_loop(self):
        while True:
            if self.writer.is_closing():
                break

            await self.context.refresh()

            message = await self.receive()

            self.context.short["__message__"] = message

            try:
                res = await self.get_chain(message.cmd)(self.context)
            except:
                raise
            else:
                await self.response(res)
                logger.info(f"{message.cmd} - {res.status_code}")