# import socket
# import struct
#
# sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock.connect(('localhost', 8080))
#
# def send(data: bytes):
#     sock.sendall(struct.pack('!I', len(data)) + data)
#
# send(b'{"status_code":101, "body":{}}')
from client import ClientFastTCP
import asyncio

async def main():
    cli = ClientFastTCP()

    @cli.route("hey")
    def hey():
        print("被访问")
        return "hey"

    await cli.connect()

    res = await cli.request("hey", "nihao!")
    print(res)

asyncio.run(main())