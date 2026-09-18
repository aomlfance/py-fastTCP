import sys_path_gloabl
from fastTCP import ClientFastTCP
from payload import *
import asyncio

cli = ClientFastTCP()

@cli.route("push_msg")
def get_msg(msg: PushMessagePayload):
    print(msg.user_name, msg.text)

async def main():
    await cli.client()
    user_name = input("your_name:")
    await cli.request("join_room", User(name=user_name))
    while True:
        await cli.request("send_msg", MessagePayload(text=input("input msg:")))

asyncio.run(main())