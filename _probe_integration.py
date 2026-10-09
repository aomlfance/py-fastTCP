"""实测新协议：test_integration 涉及的全部场景"""
import asyncio
import msgpack
from fastTCP.unification_socket import FastTCP
from fastTCP.context import Context
from pydantic import BaseModel

PORT = 9317
app = FastTCP()


@app.route("ping")
def ping():
    return "pong"


@app.route("echo")
def echo(ctx: Context):
    return ctx["payload"].body


class User(BaseModel):
    name: str
    age: int


@app.route("register")
def register(user: User):
    return f"{user.name},{user.age}"


@app.route("exists")
def exists():
    return "here"


@app.route("user.<int:id>")
def get_user(id: int):
    return f"user_{id}"


@app.route("file.<str:name>")
def get_file(name: str):
    return f"file:{name}"


@app.before("protected")
def check(ctx: Context):
    ctx.short["authed"] = True


@app.route("protected")
def protected(ctx: Context):
    return "welcome" if ctx.get("authed") else "denied"


@app.before("blocked")
def deny(ctx: Context):
    return "forbidden"


@app.route("blocked")
def blocked():
    return "should not reach"


@app.route("test_ts")
def test_ts(ctx: Context):
    return ctx.get("ts")


@app.before("*")
def add_ts(ctx: Context):
    ctx.short["ts"] = 12345


@app.route("original")
def original():
    return "first"


@app.after("original")
def add_tag(ctx: Context):
    return "tagged"


@app.route("add")
def add(ctx: Context):
    body = ctx["payload"].body
    return body.get("a", 0) + body.get("b", 0)


@app.route("str")
def str_resp():
    return "hello"


@app.route("dict")
def dict_resp():
    return {"key": "value", "count": 42}


@app.route("created")
def created():
    return "resource", 201


@app.route("empty")
def empty():
    return None


async def main():
    task = asyncio.create_task(app.serve_forever("127.0.0.1", PORT))
    await asyncio.sleep(0.3)

    cli = FastTCP()
    await cli.connect("127.0.0.1", PORT)

    cases = [
        ("ping", {}),
        ("echo", {"msg": "hello"}),
        ("register", User(name="alice", age=25)),
        ("nope", {}),
        ("user.42", {}),
        ("file.doc.txt", {}),
        ("protected", {}),
        ("blocked", {}),
        ("test_ts", {}),
        ("original", {}),
        ("add", {"a": 1, "b": 2}),
        ("hello", {}),
        ("str", {}),
        ("dict", {}),
        ("created", {}),
        ("empty", {}),
    ]
    for cmd, body in cases:
        try:
            code, b = await asyncio.wait_for(cli.request(cmd, body), 3)
            print(f"{cmd!r:22} -> {code} {b!r}")
        except Exception as e:
            print(f"{cmd!r:22} -> ERR {type(e).__name__}: {e}")

    await cli.aclose()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


asyncio.run(main())
