
from payload import *
from fastTCP import FastTCP, abort_code, Socket
import pydantic
import asyncio

app = FastTCP()

room: dict[str, Socket] = {}

@app.route("join_room")
def join_room(sock: Socket, user: User):
    if user.name in room:
        abort_code(403, "抱歉, 已经有了同名用户")
    else:
        room[user.name] = sock

@app.on_disconnect
def remove_room(orig_sock: Socket):
    for n, s in room.items():
        if s is orig_sock:
            name = n
            break
    else:
        return
    
    room.pop(name)


@app.route("send_msg")
async def send_msg(myself_sock: Socket, msg: MessagePayload):
    print(msg.text)
    for name, sock in room.items():
        if sock is myself_sock:
            continue
        await sock.request(
            "push_msg", 
            PushMessagePayload(
                user_name=name, 
                text=msg.text
            )
        )

@app.after("*")
async def none_to_ok(response):
    print

asyncio.run(app.start())