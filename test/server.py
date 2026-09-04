from fastTCP import FastTCP, Context, abort_code
import asyncio
from pydantic import BaseModel

app = FastTCP()

class User(BaseModel):
    name: str

@app.before(["hey", "hello"])
def get_name(ctx: Context, user: User):
    ctx["name"] = user.name

@app.route("hey")
def hey(name: str):
    return "hey " + name

asyncio.run(app.start())