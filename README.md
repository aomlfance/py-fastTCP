# fastTCP

> 一个风格类似fastapi, flask的python TCP框架

[![Python](https://img.shields.io/badge/Python-3.10+-blue)]()

异步, 简单, 类flask, fastapi代码风格.使写socket在写flask, fastapi般简洁.


## 事先

**fastTCP 可能不是您的最佳选择.**  
在此之前, 就有了
[Veltix](https://github.com/NytroxDev/Veltix), 
[Twisted](https://github.com/twisted/twisted) 
等成熟的python-TCP框架.  
当然, 如果你想要主流web框架的中间件链, 与更简洁简单的代码.  
你也可以选择fastTCP.

## 快速上手

```python
from fastTCP import FastTCP
import asyncio

app = FastTCP()

@app.route("hey") # or ["hey", "hi", "hello"]
def say_hello():
    return "hello"

asyncio.run(app.start())
```