class PeekError(BaseException):
    pass


class InvalidEsCommand(PeekError):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return f'Invalid ES API call. Expect format of [METHOD URL], got [{self.text}]'


class InvalidHttpMethod(PeekError):
    def __init__(self, method: str):
        self.method = method

    def __str__(self):
        return f'Invalid HTTP method: [{self.method}]'
