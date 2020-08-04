import os


class PeekError(Exception):
    pass


class PeekSyntaxError(PeekError):
    def __init__(self, text: str, error_token, title=None, message=None):
        self.text = text
        self.error_token = error_token
        self.title = title or 'Syntax error'
        self.message = message

    def __str__(self):
        text_before_error = self.text[:self.error_token.index]
        last_linesep = text_before_error.rfind(os.linesep)
        if last_linesep == -1:
            line = text_before_error
            line_index = 0
        else:
            line = text_before_error[last_linesep + len(os.linesep):]
            line_index = text_before_error.count(os.linesep)
        col_index = len(line)

        text_since_error = self.text[self.error_token.index:]
        next_linesep = text_since_error.find(os.linesep)
        if next_linesep == -1:
            line += text_since_error
        else:
            line += text_since_error[:next_linesep]

        return f'{self.title} at Line {line_index + 1}, Column {col_index + 1}:\n' \
               f'{line}\n' \
               f'{" " * col_index}' \
               f'{"^" * len(self.error_token.value)}' \
               f'{os.linesep + self.message if self.message else ""}'


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
