from .route import Blueprint
from .socket_ import Socket
import asyncio
import logging

logger = logging.getLogger(__name__)

class ClientFastTCP(Blueprint):
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.socket = None
        self._initialized = False

    @classmethod
    async def create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        await instance._async_init()
        return instance

    async def _async_init(self):
        self.socket = Socket(
            *(await asyncio.open_connection(self.host, self.port))
        )
        self._initialized = True
        asyncio.create_task(self._recv_loop())
        logger.info(f"连接到 {self.socket.address}")

    async def _recv_loop(self):
        while True:
            payload = self.socket
