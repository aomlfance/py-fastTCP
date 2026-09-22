from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .response import Response

class ExitSignal(Exception):
    """退出信号, 致命性"""
    pass

class TooBiggerSize(ExitSignal):
    pass

class Abort(Exception):
    def __init__(self, res: Response):
        self.response = res
