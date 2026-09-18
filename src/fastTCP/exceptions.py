from .payload import ResponsePayload

class ExitSignal(Exception):
    """退出信号, 致命性"""
    pass


class Abort(Exception):
    def __init__(self, res: ResponsePayload):
        self.response = res
