from typing import Any

def name(obj: Any) -> str:
    return obj.__name__ if hasattr(obj, "__name__") else str(obj)

def short_name(obj: Any):
    return repr(obj) if len(repr(obj)) < 12 else repr(obj)[:12]