from abc import ABCMeta, abstractmethod

from peek.errors import InvalidHttpMethod, InvalidEsCommand


class Command(metaclass=ABCMeta):

    @abstractmethod
    def run(self):
        """
        Execute the command
        """


class EsApiCall(Command):
    METHODS = ('GET', 'PUT', 'POST', 'DELETE')

    def __init__(self, text: str):
        fields = text.split(' ', 1)
        if len(fields) != 2:
            raise InvalidEsCommand(text)

        method = fields[0].strip().upper()
        if method not in EsApiCall.METHODS:
            raise InvalidHttpMethod(method)

        self.method = method
        self.path = fields[1].strip()
        self.payload = None

    def set_payload(self, text):
        pass

    def run(self):
        pass


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
        return EsApiCall(text)
