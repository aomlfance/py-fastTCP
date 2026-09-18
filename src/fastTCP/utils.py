from typing import Callable, Any

def get_callable_name(obj: Callable) -> str:
    return obj.__name__ if hasattr(obj, "__name__") else str(obj)

LEN_TO = 12

def clipping_strings(string: str, len_to: int = LEN_TO) -> str:
    return string if len(string) < len_to else string[:len_to]

