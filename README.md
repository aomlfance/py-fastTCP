# fastTCP

> 一个风格类似 FastAPI / Flask 的 Python TCP 框架

![Python](https://img.shields.io/badge/Python-3.14+-blue)

> [!NOTE]
> 并非依赖了3.14以上的模块, 而是基于[PEP 649](https://peps.python.org/pep-0649/)进行开发.  
> 实际支持仍在python3.10+

异步、简洁、类 Flask/FastAPI 代码风格，让写 TCP 像写 Web 框架一样简单。

## 特性

fastTCP秉承着fastapi的设计理念

- **装饰器路由** — `@app.route("cmd")` 注册路由，和 Flask 一样直观
- **通配符路由** — `<int:id>`、`<str:name>`、`*` 全局匹配
- **中间件链** — `before` / `after` 分别在路由前后执行
- **依赖注入** — 根据函数签名自动注入参数
<!--**蓝图** — 支持模块化拆分路由-->
<!--**生成器对话** — 用 `yield` 实现多轮交互式对话-->

## 事先

**该项目仍在开发阶段, 尚未定型**

## 安装

```bash
git clone https://github.com/aomlfance/py-fastTCP.git
cd py-fastTCP
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 快速上手

### 服务端

```python
from src.fastTCP import FastTCPServer, _Context
import pydantic
import asyncio

app = FastTCPServer(host="127.0.0.1", port=8964)


class User(pydantic.BaseModel):
    name: str


@app.route("hey")
def hey(user: User):
    return f"hey {user.name}"


asyncio.run(app.serve_forever())
```

### 客户端

```python
from client import ClientFastTCP
import pydantic
import asyncio

cli = ClientFastTCP()


class User(pydantic.BaseModel):
    name: str


@cli.route("hey")
def hey():
    return "hey server"


async def main():
    await cli.connect()
    res = await cli.request("hey", User(name="user"))
    print(res.body.get("data"))


asyncio.run(main())
```

## 路由

### 基本路由

```python
@app.route("hello")
def hello():
    return "hello"

@app.route(["hey", "hi", "hello"])
def greet():
    return "hi"
```

### 通配符路由

```python
@app.route("user.<int:id>")
def get_user(id: int):
    return f"user {id}"

@app.route("file.<str:name>")
def get_file(name: str):
    return f"file {name}"
```

支持的类型：`int`、`str`（默认）、`uuid`

### 返回值

```python
# 字符串 → 自动包装为 {"data": "hello"}
@app.route("str")
def str_resp():
    return "hello"

# 字典 → 直接作为 body
@app.route("dict")
def dict_resp():
    return {"key": "value"}

# 元组 → (body, status_code)
@app.route("created")
def tuple_resp():
    return "created", 201
```

## 中间件

### before — 路由前执行

```python
@app.before("hey")
def check_auth(ctx: Context):
    if "token" not in ctx.payload.body:

        abort_code(401)
    ctx["user"] = verify_token(ctx.payload.body["token"])
```

`before` 路由返回值会**短路**后续执行（main 路由不会跑）。

### after — 路由后执行

```python
@app.after("hey")
def log_response(ctx: Context, response: ResponsePayload):
    print(f"请求完成: {ctx.payload.cmd}")
    return {"logged": True}
```

### 全局中间件
```python
@app.before("*")
def global_before(ctx: Context):
    ctx["start_time"] = time.time()

@app.after("*")
def global_after(ctx: Context):
    print(f"耗时: {time.time() - ctx['start_time']}s")
```

> [!NOTE]
> 由于蓝图尚未定型, 有关可能在蓝图中的`bp.before("*")`产生的歧义仍在裁定

## 依赖注入

框架根据函数签名自动注入参数：

```python
# Context — 自动注入上下文
@app.route("test")
def test(ctx: Context):
    return ctx.payload.cmd

# pydantic 模型 — 自动从 body 绑定
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

@app.route("register")
def register(user: User):
    return f"{user.name}, {user.age}岁"

# 字符串/数字 — 从 store 中按名注入
@app.before("greet")
def set_name(ctx: Context):
    ctx["name"] = ctx.payload.body.get("name", "guest")

@app.route("greet")
def greet(name: str):
    return f"hello {name}"
```

## 生成器对话

> [!WARNING]
> **关于原生成器对话**  
> 该部分内容还在审计是否公开api

## 短路处理

```python
from response import abort_code, abort_args


@app.route("forbidden")
def forbidden():
    abort_code(403)


@app.route("error")
def error():
    abort_args("参数错误", 422)
```

## 协议格式

```
请求: {"cmd": "路由名", "body": {任意数据}}
响应: {"status_code": 状态码, "body": {响应数据}}
```

> [!WARNING]
> 关于协议, 正打算迭代为MessagePack处理序列化.

状态码复用 HTTP 状态码体系（200 成功、404 未找到、500 服务器错误等）。