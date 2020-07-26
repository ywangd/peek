class PeekError(Exception):
    pass


class PeekSyntaxError(PeekError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f'Syntax error: [{self.value}]'


class InvalidEsApiCall(PeekError):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return f'Invalid ES API call. Expect format of "METHOD URL [PAYLOAD]", got [{self.text}]'


class InvalidHttpMethod(PeekError):
    def __init__(self, method: str):
        self.method = method

    def __str__(self):
        return f'Invalid HTTP method: [{self.method}]'
