import socket
import json
import struct

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 8964))

def send_msg(obj):
    bytes_msg = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack("!I", len(bytes_msg)) + bytes_msg)

send_msg({"cmd":"hey", "body":{"name":"FastTCP"}})

print(sock.recv(1024))