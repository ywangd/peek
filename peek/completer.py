from typing import Iterable

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter
from prompt_toolkit.document import Document

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)


class PeekCompleter(Completer):

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        for c in document.text.lstrip():
            if c.isspace():
                return []
        else:
            return _HTTP_METHOD_COMPLETER.get_completions(document, complete_event)


