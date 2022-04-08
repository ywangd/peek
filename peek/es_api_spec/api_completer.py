from abc import ABCMeta, abstractmethod
from typing import List, Tuple

from prompt_toolkit.completion import Completion, CompleteEvent
from prompt_toolkit.document import Document

from peek.common import PeekToken
from peek.parser import ParserEvent


class ESApiCompleter(metaclass=ABCMeta):
    @abstractmethod
    def complete_url_path(self, document: Document, complete_event: CompleteEvent, method: str,
                          path_tokens: List[PeekToken]) -> List[Completion]:
        pass

    @abstractmethod
    def complete_query_param_name(self, document: Document, complete_event: CompleteEvent, method: str,
                                  path_tokens: List[PeekToken]) -> List[Completion]:
        pass

    @abstractmethod
    def complete_query_param_value(self, document: Document, complete_event: CompleteEvent, method: str,
                                   path_tokens: List[PeekToken]) -> List[Completion]:
        pass

    @abstractmethod
    def complete_payload(self, document: Document, complete_event: CompleteEvent, method: str,
                         path_tokens: List[PeekToken],
                         payload_tokens: List[PeekToken],
                         payload_events: List[ParserEvent]) -> Tuple[List[Completion], dict]:
        pass

    @abstractmethod
    def complete_payload_value(self, document: Document, complete_event: CompleteEvent, method: str,
                               path_tokens: List[PeekToken],
                               payload_tokens: List[PeekToken],
                               payload_events: List[ParserEvent]) -> Tuple[List[Completion], dict]:
        pass


def can_match(ts, ps):
    """
    Test whether the input path (ts) can match the candidate path (ps).
    The rule is basically a placeholder can match any string other than
    the ones leading with underscore.
    """
    for t, p in zip(ts, ps):
        if t != p:
            if t.startswith('_'):
                return False
            if not (p.startswith('{') and p.endswith('}')):
                return False
    return True
