import ast
import string
from abc import ABCMeta, abstractmethod

from peek.errors import InvalidHttpMethod, InvalidEsCommand


class Command(metaclass=ABCMeta):

    @abstractmethod
    def execute(self):
        """
        Execute the command
        """


class EsApiCommand(Command):
    _METHODS = ('GET', 'PUT', 'POST', 'DELETE')

    def __init__(self, text: str):
        self.source = text
        self.method, self.path, self.payload = self._parse()

    def execute(self, client):
        return client.execute_command(self)

    def _parse(self):
        fields = self.source.split(' ', 1)
        if len(fields) != 2:
            raise InvalidEsCommand(self.source)

        for i, c in enumerate(fields[1]):
            if c in string.whitespace:
                path, payload = fields[1][:i].strip(), fields[1][i:].strip()
                break
        else:
            path = fields[1]
            payload = ''

        method = fields[0].strip().upper()
        if method not in EsApiCommand._METHODS:
            raise InvalidHttpMethod(method)

        return (
            method,
            path if path.startswith('/') else f'/{path}',
            ast.literal_eval(payload) if payload else None
        )


class PeekCommand:
    LEADING_CHAR = '%'

    def __init__(self, text: str):
        self.source = text[1:].strip()

    def run(self):
        pass


def new_command(text: str):
    text = text.strip()
    if text.startswith(PeekCommand.LEADING_CHAR):
        return PeekCommand(text)
    else:
        return EsApiCommand(text)
