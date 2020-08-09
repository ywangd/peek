import itertools
import json
import logging
import os
from typing import Iterable

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter, FuzzyCompleter
from prompt_toolkit.document import Document
from pygments.token import Error, Name

from peek.lexers import PeekLexer, UrlPathLexer, PathPart, ParamName, Ampersand, QuestionMark, Slash, HttpMethod, \
    FuncName, BlankLine, KeyName, Assign
from peek.names import NAMES
from peek.parser import process_tokens

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)

_FUNC_NAME_COMPLETER = WordCompleter(sorted(NAMES.keys()))

_ES_API_CALL_OPTION_COMPLETER = WordCompleter([w + '=' for w in sorted(['conn', 'runas'])])


class PeekCompleter(Completer):

    def __init__(self):
        self.lexer = PeekLexer()
        self.url_path_lexer = UrlPathLexer()
        from peek import __file__ as package_root
        package_root = os.path.dirname(package_root)
        kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')
        self.specs = load_specs(kibana_dir)

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
                _logger.debug(f'Found token {t} at {i} for completion')
                break
        else:
            _logger.debug(f'cursor is after the last token')
            # Cursor is on whitespace after the last non-white token
            if text[tokens[-1].index + len(tokens[-1].value):].find('\n') != -1:
                return []  # cursor is on separate line
            elif tokens[-1].ttype is HttpMethod:  # do not complete yet, wait for first char for path
                return []
            else:
                # Cursor is at the end of an ES API or func call
                _logger.debug('cursor is at the end of a statement')
                return self._complete_options(tokens, document, complete_event)

        if t.ttype in (HttpMethod, FuncName):
            _logger.debug(f'Completing function/http method name: {t}')
            return itertools.chain(
                _HTTP_METHOD_COMPLETER.get_completions(document, complete_event),
                _FUNC_NAME_COMPLETER.get_completions(document, complete_event))

        # The token right before cursor is HttpMethod, go for path completion
        if i > 0 and tokens[i - 1].ttype is HttpMethod:
            return self._complete_path(tokens, document, complete_event)

        # The token is a KeyName or Error (incomplete k=v form), try complete for options
        if t.ttype in (Error, KeyName, Name):
            return self._complete_options(tokens[:-1], document, complete_event)

        return []

    def _complete_path(self, tokens, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        method_token, path_token = tokens[-2], tokens[-1]
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
            return self._comoplete_query_param_value(method, path_tokens, document, complete_event)

    def _complete_path_part(self, method, path_tokens, document: Document, complete_event: CompleteEvent):
        cursor_token = path_tokens[-1]
        _logger.debug(f'Completing path part: {cursor_token}')
        ts = [t.value for t in path_tokens if t.ttype is not Slash]
        if cursor_token.ttype is PathPart:
            ts.pop()
        _logger.debug(f'ts: {ts}')
        candidates = []
        for api_name, api_spec in self.specs.items():
            if method not in api_spec['methods']:
                continue
            for api_path in api_spec['patterns']:
                ps = [p for p in api_path.split('/') if p]
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
            if method not in api_spec['methods']:
                continue
            if not api_spec.get('url_params', None):
                continue
            for api_path in api_spec['patterns']:
                ps = [p for p in api_path.split('/') if p]
                if len(ts) != len(ps):
                    continue
                if not can_match(ts, ps):
                    continue
                candidates.update(api_spec['url_params'].keys())

        return FuzzyCompleter(ConstantCompleter(
            [Completion(c, start_position=0) for c in candidates])).get_completions(document, complete_event)

    def _comoplete_query_param_value(self, method, path_tokens, document: Document, complete_event: CompleteEvent):
        _logger.debug(f'Completing query param value: {path_tokens[-1]}')
        try:
            param_name_token = path_tokens[-2] if path_tokens[-1].ttype is Assign else path_tokens[-3]
        except IndexError as e:
            _logger.error(f'{path_tokens}')
            _logger.error(e)
        _logger.debug(f'Param name token: {param_name_token}')
        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_name, api_spec in self.specs.items():
            if method not in api_spec['methods']:
                continue
            if not api_spec.get('url_params', None):
                continue
            for api_path in api_spec['patterns']:
                ps = [p for p in api_path.split('/') if p]
                if len(ts) != len(ps):
                    continue
                if not can_match(ts, ps):
                    continue
                v = api_spec['url_params'].get(param_name_token.value, None)
                if v is None:
                    continue
                if v == '__flag__':
                    candidates.update(('true', 'false'))
                elif isinstance(v, list) and len(v) > 0:
                    candidates.update(v)
        return FuzzyCompleter(ConstantCompleter(
            [Completion(c, start_position=0) for c in candidates])).get_completions(document, complete_event)

    def _complete_options(self, tokens, document: Document, complete_event: CompleteEvent):
        _logger.debug('Completing for options')
        # If directly after a =, it is a value, no completion needed
        if len(tokens) > 0 and tokens[-1].ttype is Assign:
            # TODO: complete for variable names
            return []

        # TODO: For future handle the KeyName or Name is inside a function call, e.g. f(name=..)
        for t in tokens[::-1]:
            if t.ttype is HttpMethod:
                return _ES_API_CALL_OPTION_COMPLETER.get_completions(document, complete_event)
            elif t.ttype is FuncName:
                func = NAMES.get(t.value)
                if func is None or not getattr(func, 'option_names', None):
                    return []
                return WordCompleter(sorted([n + '=' for n in func.option_names])).get_completions(
                    document, complete_event)
            elif t.ttype is BlankLine:
                return []

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


def load_specs(kibana_dir):
    oss_path = os.path.join(
        kibana_dir, 'src', 'plugins', 'console', 'server', 'lib', 'spec_definitions')
    xpack_path = os.path.join(
        kibana_dir, 'x-pack', 'plugins', 'console_extensions', 'server', 'lib', 'spec_definitions')
    specs = _load_json_specs(os.path.join(oss_path, 'json'))
    specs.update(_load_json_specs(os.path.join(xpack_path, 'json')))
    return specs


def _load_json_specs(base_dir):
    specs = {}
    for sub_dir in ('generated', 'overrides'):
        d = os.path.join(base_dir, sub_dir)
        if not os.path.exists(d):
            _logger.warning(f'JSON specs directory does not exist: {d}')
            continue
        for f in os.listdir(d):
            if f == '_common.json':
                continue
            with open(os.path.join(d, f)) as ins:
                spec = json.load(ins)
            if sub_dir == 'generated':
                specs.update(spec)
            else:
                for k, v in spec.items():
                    if k in specs:
                        specs[k].update(v)
                    else:
                        if k.startswith('xpack.'):
                            specs[k[6:]].update(v)
                        else:
                            specs['xpack.' + k].update(v)

    return specs
