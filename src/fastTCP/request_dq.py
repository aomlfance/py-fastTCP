import collections
import asyncio

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from .socket_ import RequestMessage, ResponseMessage

@final
class RequestDequeManager:
    def __init__(self):
        self._req_dq = collections.deque()

    def enqueue(self) -> asyncio.Future[ResponseMessage]:
        fut = asyncio.get_running_loop().create_future()
        self._req_dq.append(fut)
        return fut

    def dequeue(self, response: ResponseMessage):
        if not self._req_dq:
            raise IndexError("deque is empty")

        fut = self._req_dq.popleft()

        if not fut.done():
            fut.set_result(response)

    def can_dequeue(self) -> bool:
        return bool(self._req_dq)
