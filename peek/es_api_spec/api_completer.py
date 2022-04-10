import ast
import json
import logging
from abc import ABCMeta, abstractmethod
from typing import List, Tuple

from prompt_toolkit.completion import Completion, CompleteEvent
from prompt_toolkit.document import Document
from pygments.token import String, Name

from peek.common import PeekToken
from peek.es_api_spec.schema import Schema
from peek.lexers import Slash, PathPart, Assign, CurlyLeft, CurlyRight, DictKey, EOF, Colon, BracketLeft, Comma
from peek.parser import ParserEvent, ParserEventType

_logger = logging.getLogger(__name__)


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


class SchemaESApiCompleter(ESApiCompleter):

    def __init__(self):
        self._schema = Schema()

    def complete_url_path(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        cursor_token = path_tokens[-1]
        _logger.debug(f'Completing URL path: {cursor_token}')
        token_stream = [t.value for t in path_tokens if t.ttype is not Slash]
        if cursor_token.ttype is PathPart:
            token_stream.pop()
        return [Completion(c)
                for c in self._schema.candidate_urls(method, token_stream)]

    def complete_query_param_name(self, document, complete_event, method, path_tokens):
        _logger.debug(f'Completing URL query param name: {path_tokens[-1]}')
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        return [Completion(c)
                for c in self._schema.candidate_query_param_names(method, token_stream)]

    def complete_query_param_value(self, document, complete_event, method, path_tokens):
        _logger.debug(f'Completing URL query param value: {path_tokens[-1]}')
        param_name_token = path_tokens[-2] if path_tokens[-1].ttype is Assign else path_tokens[-3]
        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        return [Completion(c)
                for c in
                self._schema.candidate_query_param_values(method, ts, param_name_token.value)]

    def complete_payload(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        _logger.debug(f'Completing for API payload: {method!r} {path_tokens!r} {payload_tokens!r}')
        # TODO: refactor with parser state tracker
        payload_keys = []
        curly_level = 0
        for t in payload_tokens[:-1]:
            if t.ttype is CurlyLeft:
                curly_level += 1
            elif t.ttype is CurlyRight:
                curly_level -= 1
                payload_keys.pop()
            elif t.ttype is DictKey:
                if len(payload_keys) == curly_level - 1:
                    payload_keys.append(ast.literal_eval(t.value))
                elif len(payload_keys) == curly_level:
                    payload_keys[-1] = ast.literal_eval(t.value)
                else:
                    raise ValueError(f'Error when counting curly level {curly_level} and keys {payload_keys}')

        _logger.debug(f'Payload status: level: {curly_level}, keys: {payload_keys}')
        if curly_level == 0:  # not even in the first curly bracket, no completion
            return [], {}

        # Remove the payload key that is at the same level
        if curly_level == len(payload_keys):
            payload_keys.pop()

        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        name_to_values = self._schema.candidate_keys(method, ts, payload_keys)
        return [Completion(c) for c in sorted(name_to_values.keys())], name_to_values

    def complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        _logger.debug(f'Completing for API payload value: {method!r} {path_tokens!r} {payload_tokens!r}')
        completions = self._do_complete_payload_value(document, complete_event, method, path_tokens,
                                                      payload_tokens, payload_events)
        return [Completion(c) for c in sorted(set(completions))], {}

    def _do_complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        unpaired_dict_key_tokens = []
        for payload_event in payload_events:
            if payload_event.type is ParserEventType.BEFORE_DICT_KEY_EXPR:
                _logger.debug(f'No completion is possible for payload with dict key expr: {payload_event.token}')
                return []
            elif payload_event.type is ParserEventType.DICT_KEY:
                unpaired_dict_key_tokens.append(payload_event.token)
            elif payload_event.type is ParserEventType.AFTER_DICT_VALUE and payload_event.token.ttype is not EOF:
                unpaired_dict_key_tokens.pop()

        if not unpaired_dict_key_tokens:  # should not happen
            _logger.warning('No unpaired dict key tokens are found')
            return []

        payload_keys = [ast.literal_eval(t.value) for t in unpaired_dict_key_tokens]
        _logger.debug(f'Payload keys are: {payload_keys}')

        # Find last Colon position
        for index_colon in range(len(payload_tokens) - 1, -1, -1):
            if payload_tokens[index_colon].ttype is Colon:
                break
        else:
            _logger.warning(f'Should not happen - Colon not found in payload: {payload_tokens}')
            return []

        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        if index_colon == len(payload_tokens) - 1:  # Colon is the last token
            _logger.debug('Colon is the last token')
            # The simpler case when value position has nothing yet
            return [json.dumps(v) for v in self._schema.candidate_values(method, ts, payload_keys)]
        else:
            token_after_colon = payload_tokens[index_colon + 1]
            last_payload_token = payload_tokens[-1]
            _logger.debug(f'The token after colon is: {token_after_colon}, last payload_token is: {last_payload_token}')
            if token_after_colon.ttype is BracketLeft:
                if last_payload_token.ttype is BracketLeft or last_payload_token.ttype is Comma:
                    # no question asked, let's complete
                    values = self._schema.candidate_values(method, ts, payload_keys, inside_array=True)
                    return [json.dumps(v) for v in values]
                elif last_payload_token.ttype in String:
                    try:
                        ast.literal_eval(last_payload_token.value)
                    except SyntaxError:
                        # String is not complete, i.e. we are completing the string under cursor
                        values = self._schema.candidate_values(method, ts, payload_keys, inside_array=True)
                        return [v for v in values if isinstance(v, str)]

            elif token_after_colon.ttype in String and token_after_colon is last_payload_token:
                return [v for v in self._schema.candidate_values(method, ts, payload_keys) if isinstance(v, str)]
            elif token_after_colon.ttype is Name and token_after_colon is last_payload_token:
                return [json.dumps(v)
                        for v in self._schema.candidate_values(method, ts, payload_keys) if v in (True, False, None)]

        return []  # catch all
