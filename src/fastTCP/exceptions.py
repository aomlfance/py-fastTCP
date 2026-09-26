from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .response import ResponseMessage

class ExitSignal(Exception):
    """退出信号, 致命性"""
    pass

class Abort(Exception):
    def __init__(self, res: ResponseMessage):
        self.response = res
