import asyncio
from collections import deque

dq = deque()   # 每个元素: (data, future)


def enqueue(data):
    """请求进来：入队，并返回一个 future 供等待"""
    fut = asyncio.get_running_loop().create_future()
    dq.append((data, fut))
    return fut


def dequeue(response):
    """响应回来：消费队首元素，用 response 唤醒对应协程"""
    if not dq:
        raise IndexError("队列为空，没有等待中的请求")
    data, fut = dq.popleft()
    if not fut.done():
        fut.set_result(response)   # 唤醒等这个元素的协程
    return data


async def request(data):
    """发请求，等它的响应"""
    fut = enqueue(data)
    print(f"请求 {data} 已发出，等待响应...")
    response = await fut               # 挂起，直到 dequeue 唤醒
    print(f"请求 {data} 收到响应: {response}")
    return response

async def client():
    # 三个请求按顺序发出
    await asyncio.gather(
        request("req-1"),
        request("req-2"),
        request("req-3"),
    )

async def server():
    # 模拟响应按顺序回来
    await asyncio.sleep(0.1)
    dequeue("resp-1")   # 唤醒等 req-1 的协程
    await asyncio.sleep(0.1)
    dequeue("resp-2")   # 唤醒等 req-2 的协程
    await asyncio.sleep(0.1)
    dequeue("resp-3")   # 唤醒等 req-3 的协程


async def main():
    await asyncio.gather(client(), server())


asyncio.run(main())