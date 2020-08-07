import itertools
import json
import logging
import os
from typing import Iterable

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter, FuzzyCompleter
from prompt_toolkit.document import Document
from pygments.token import Keyword

from peek.lexers import PeekLexer, UrlPathLexer, PathPart, ParamName, Ampersand, QuestionMark, Slash
from peek.names import NAMES
from peek.parser import process_tokens

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)

_FUNC_NAME_COMPLETER = WordCompleter(list(NAMES.keys()))


class PeekCompleter(Completer):

    def __init__(self):
        self.lexer = PeekLexer()
        self.url_path_lexer = UrlPathLexer()
        self.specs = load_rest_api_spec()

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        _logger.debug(f'doc: {document}, event: {complete_event}')

        text = document.text[:document.cursor_position]
        _logger.debug(f'text: {text!r}')

        # Merge consecutive error tokens
        tokens = process_tokens(self.lexer.get_tokens_unprocessed(text))
        _logger.debug(f'tokens: {tokens}')

        if len(tokens) == 0:
            return []

        # Find which token to complete
        for i, t in enumerate(tokens):
            if t.index < document.cursor_position <= (t.index + len(t.value)):
                break
        else:
            return []

        if i == 0:
            _logger.debug(f'Completing function/http method name: {t}')
            return itertools.chain(
                _HTTP_METHOD_COMPLETER.get_completions(document, complete_event),
                _FUNC_NAME_COMPLETER.get_completions(document, complete_event))

        if i == 1 and tokens[0].ttype is Keyword:
            return self._complete_path(tokens, document, complete_event)

        return []

    def _complete_path(self, tokens, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        method_token, path_token = tokens
        method = method_token.value.upper()
        cursor_position = document.cursor_position - path_token.index
        path = path_token.value[:cursor_position]
        _logger.debug(f'Completing http path: {path}')
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path))
        if not path_tokens:  # empty, should not happen
            return []

        cursor_token = path_tokens[-1]
        _logger.debug(f'cursor_token: {cursor_token}')
        if cursor_token.ttype in (PathPart, Slash):
            return self._complete_path_part(method, path_tokens, document, complete_event)
        elif cursor_token.ttype in (ParamName, QuestionMark, Ampersand):
            return self._complete_query_param_name(method, path_tokens, document, complete_event)
        else:  # skip for param value
            return []

    def _complete_path_part(self, method, path_tokens, document: Document, complete_event: CompleteEvent):
        cursor_token = path_tokens[-1]
        _logger.debug(f'Completing path part: {cursor_token}')
        ts = [t.value for t in path_tokens if t.ttype is not Slash]
        if cursor_token.ttype is PathPart:
            ts.pop()
        _logger.debug(f'ts: {ts}')
        candidates = []
        for api_name, api_spec in self.specs.items():
            for api_path in api_spec['url']['paths']:
                if method not in api_path['methods']:
                    continue
                ps = [p for p in api_path['path'].split('/') if p]
                # Nothing to complete if the candidate is shorter than current input
                if len(ts) >= len(ps):
                    continue
                if not can_match(ts, ps):
                    continue
                candidate = '/'.join(ps[len(ts):])
                candidates.append(Completion(candidate, start_position=0))

        return FuzzyCompleter(ConstantCompleter(candidates)).get_completions(document, complete_event)

    def _complete_query_param_name(self, method, path_tokens, document: Document, complete_event: CompleteEvent):
        _logger.debug(f'Completing query param name: {path_tokens[-1]}')
        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_name, api_spec in self.specs.items():
            for api_path in api_spec['url']['paths']:
                if method not in api_path['methods']:
                    continue
                if not api_spec.get('params', None):
                    continue
                ps = [p for p in api_path['path'].split('/') if p]
                if len(ts) != len(ps):
                    continue
                if not can_match(ts, ps):
                    continue
                candidates.update(api_spec['params'].keys())

        return FuzzyCompleter(ConstantCompleter(
            [Completion(c, start_position=0) for c in candidates])).get_completions(document, complete_event)

    def _complete_payload(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        # TODO: payload completion
        return []


def can_match(ts, ps):
    for t, p in zip(ts, ps):
        if t != p:
            if t.startswith('_'):
                return False
            if not (p.startswith('{') and p.endswith('}')):
                return False
    return True


class ConstantCompleter(Completer):

    def __init__(self, candidates):
        self.candidates = candidates

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        return self.candidates


def load_rest_api_spec():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    spec_dir = os.path.join(package_root, 'rest-api-spec', 'api')
    if not os.path.exists(spec_dir):
        _logger.warning(f'spec directory does not exist: {spec_dir}')
        return {}
    spec_files = [f for f in os.listdir(spec_dir) if f.endswith('.json')]
    specs = {}
    for spec_file in spec_files:
        if spec_file == '_common.json':
            continue
        with open(os.path.join(spec_dir, spec_file)) as ins:
            specs.update(json.load(ins))
    return specs
