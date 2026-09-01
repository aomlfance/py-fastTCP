from fastTCP import FastTCP, Context, abort_code
import asyncio

app = FastTCP()

@app.before(["hey", "hello"])
def get_name(ctx: Context):
    if "name" not in ctx.payload.body:
        abort_code(400)

    ctx["name"] = ctx.payload.body["name"]

@app.route("hey")
def hey(ctx: Context, name: str):
    return "hey " + name

asyncio.run(app.start())