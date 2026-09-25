import inspect
from fastTCP.context import Context

def handler(ctx: Context):
    pass

sig = inspect.signature(handler)
for name, param in sig.parameters.items():
    print(f"param.name={name}")
    print(f"param.annotation={param.annotation}")
    print(f"type={type(param.annotation)}")
    print(f"== Context? {param.annotation == Context}")
    print(f"is Context? {param.annotation is Context}")
