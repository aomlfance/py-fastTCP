from typing import Any
from .payload import RequestPayload, ResponsePayload
from .route import Blueprint
from .socket_ import Socket
from .frame import run_chain
from .context import Context
from .request import make_requests
from collections import deque
import asyncio
import logging

logger = logging.getLogger(__name__)

class ClientFastTCP(Blueprint):
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        super().__init__()
        self.host = host
        self.port = port
        self._socket: Socket | None = None
        self._initialized = False
        self._req_dp = deque()

    def _enqueue(self):
        fut = asyncio.get_running_loop().create_future()
        self._req_dp.append(fut)
        return fut

    def _dequeue(self, response: ResponsePayload):
        if not self._req_dp:
            raise IndexError("deque is empty")
        fut = self._req_dp.popleft()
        if not fut.done():
            fut.set_result(response)

    async def request(self, cmd: str, body: Any) -> ResponsePayload:
        req = make_requests(cmd, body)

        await self.socket.send_payload(req)
        fut = self._enqueue()
        return await fut

    @property
    def socket(self) -> Socket:
        """使_socket的结果幂等"""
        if self._socket is None:
            raise RuntimeError("_socket未初始化")
        return self._socket

    async def client(self):
        self._socket = Socket(
            *(await asyncio.open_connection(self.host, self.port))
        )

        self._initialized = True

        asyncio.create_task(self._recv_loop())
        logger.info(f"连接到 {self.socket.address}")

    # 想一下我们的业务场景, 假如如果客户端要 request, response, (bytes先不支持)
    async def _recv_loop(self):
        while True:
            if self.socket.stream_writer.is_closing():
                break

            payload: RequestPayload | ResponsePayload = await self.socket.get_payload([RequestPayload, ResponsePayload])

            if isinstance(payload, ResponsePayload):
                if not self._req_dp:
                    logger.warning("没有在等待的队列")
                    continue
                self._dequeue(payload)
                continue

            context = Context(self.socket, payload)

            try:
                res = await run_chain(context, self.get_chain(payload.cmd))
            except:
                raise
            else:
                await self.socket.send_payload(res)
                logger.info(f"{payload.cmd} - {res.status_code}")
