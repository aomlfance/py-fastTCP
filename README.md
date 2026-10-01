# fastTCP

> 一个风格类似 FastAPI 的 Python TCP 框架

![Python](https://img.shields.io/badge/Python-3.14+-blue)

> [!NOTE]
> 并非依赖了3.14以上的模块, 而是基于[PEP 649](https://peps.python.org/pep-0649/)进行开发.  
> 实际支持仍在python3.10+

异步、简洁、类 FastAPI 代码风格，让写 TCP 像写 Web 框架一样简单。

## 特性

fastTCP秉承着fastapi的设计理念

- **装饰器路由** — `@app.route("cmd")` 注册路由，和 Flask 一样直观
- **通配符路由** — `<int:id>`、`<str:name>`、`*` 全局匹配
- **中间件链** — `before` / `after` 分别在路由前后执行
- **依赖注入** — 根据函数签名自动注入参数
<!--**蓝图** — 支持模块化拆分路由-->
<!--**生成器对话** — 用 `yield` 实现多轮交互式对话-->

## 事先

**该项目已有雏形, 仍在完善阶段**

## 安装

```bash
git clone https://github.com/aomlfance/py-fastTCP.git
cd py-fastTCP
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 简单的例子
server
```python
from fastTCP import FastTCPServer
import asyncio

app = FastTCPServer()

@app.route("hello")
def hello(name: str): # 由消息注入
    return f"hello {name}"

asyncio.run(app.serve_forever())
```
client
```python
from fastTCP import ClientFastTCP
import asyncio

client = ClientFastTCP()

name = "FastTCP"

async def main():
    await client.connect()
    res = await client.request("hello", name)
    print(res.body)

asyncio.run(main())
```