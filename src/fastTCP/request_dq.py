import collections
import asyncio
from .payload import ResponsePayload

class RequestDequeManager:
    def __init__(self):
        self._req_dq = collections.deque()

    def enqueue(self):
        fut = asyncio.get_running_loop().create_future()
        self._req_dq.append(fut)
        return fut

    def dequeue(self, response: ResponsePayload):
        if not self._req_dq:
            raise IndexError("deque is empty")

        fut = self._req_dq.popleft()

        if not fut.done():
            fut.set_result(response)

    def can_dequeue(self) -> bool:
        return bool(self._req_dq)

    def __init_subclass__(cls) -> None:
        raise TypeError("Inheritance is not allowed in this class.")