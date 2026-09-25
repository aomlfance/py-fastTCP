from typing import Any
from .payload import RequestPayload, ResponsePayload
from .route import Blueprint
from .context import _Context
from .request import make_requests
from .request_dq import RequestDequeManager
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

        self._req_dq_mg = RequestDequeManager()

        self.host = host
        self.port = port
        self._socket: _Socket | None = None
        self.context = _Context()

    async def request(self, cmd: str, body: Any) -> ResponsePayload:
        req = make_requests(cmd, body)

        await self.send_payload(req)

        fut = self._req_dq_mg.enqueue()

        return await fut

    async def connect(self):
        _Socket.__init__(self, self._req_dq_mg, *(await asyncio.open_connection(self.host, self.port)))

        self.context.long["socket"] = self

        asyncio.create_task(self._recv_loop())

        logger.info(f"连接到 {self.address}")

    async def _recv_loop(self):
        while True:
            if self.stream_writer.is_closing():
                break

            self.context.refresh()

            payload: RequestPayload | ResponsePayload = await self.get_payload([RequestPayload, ResponsePayload])

            self.context.short["payload"] = payload

            if isinstance(payload, ResponsePayload):

                if not self._req_dq_mg.can_dequeue():
                    continue

                self._req_dq_mg.dequeue(payload)
                continue

            try:
                res = await self.get_chain(payload.cmd)(self.context)
            except:
                raise
            else:
                await self.send_payload(res)
                logger.info(f"{payload.cmd} - {res.status_code}")