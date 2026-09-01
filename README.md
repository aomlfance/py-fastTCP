# fastTCP

> 一个风格类似fastapi, flask的tcp框架

## 开发者预览
该项目还在不断的快速迭代, **未来将出现破坏兼容性的变更**, 请等待正式版.

## 快速开始

```python
from fastTCP import FastTCP, Context
import asyncio

app = FastTCP()


@app.route("hello")
def hello(ctx: Context):  # 也可以是异步函数
    return "Hello World"


asyncio.run(app.start())
```

`fastTCP`默认运行在本地的`127.0.0.1`的`8964`端口上.  
如果想要修改, 需要修改类属性

```python
from fastTCP import FastTCP

FastTCP.host = "127.89.0.64"
FastTCP.port = 1989
```

并且`fastTCP`
