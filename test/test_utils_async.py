from typing import Literal
from src.fastTCP.utils import Async

def hello(name: str, gender: Literal["man", "woman"]):
    print(f"hello {gender}, {name}")

async def test_main():
    await Async(hello)("fastTCP", "man")
