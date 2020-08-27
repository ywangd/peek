import ast
import itertools
import json
import logging
import os
from typing import Iterable, List, Dict, Tuple, Optional

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter, FuzzyCompleter, PathCompleter
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.document import Document
from pygments.token import Error, Name, Literal, String

from peek.common import PeekToken
from peek.errors import PeekError
from peek.lexers import PeekLexer, UrlPathLexer, PathPart, ParamName, Ampersand, QuestionMark, Slash, HttpMethod, \
    FuncName, OptionName, Assign, CurlyLeft, CurlyRight, DictKey, ShellOut, At
from peek.parser import process_tokens

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)

_ES_API_CALL_OPTION_COMPLETER = WordCompleter([w + '=' for w in sorted(['conn', 'runas', 'headers', 'xoid'])])

_PATH_COMPLETER = PathCompleter(expanduser=True)
_SYSTEM_COMPLETER = SystemCompleter()


class PeekCompleter(Completer):

    def __init__(self, app):
        self.app = app
        self.lexer = PeekLexer()
        self.url_path_lexer = UrlPathLexer()
        from peek import __file__ as package_root
        package_root = os.path.dirname(package_root)
        kibana_dir = app.config['kibana_dir'] or os.path.join(package_root, 'specs', 'kibana-7.8.1')
        if self.app.config.as_bool('load_api_specs'):
            self.specs = load_specs(kibana_dir)
        else:
            self.specs = {}

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        _logger.debug(f'doc: {document}, event: {complete_event}')

        text = document.text_before_cursor
        _logger.debug(f'text before cursor: {text!r}')

        # Parse tokens for only the text before cursor and merge certain consecutive tokens
        tokens = process_tokens(self.lexer.get_tokens_unprocessed(text))
        _logger.debug(f'processed tokens: {tokens}')

        # Nothing to complete if no significant tokens are found
        if len(tokens) == 0:
            return []

        idx_head_token, head_token = find_beginning_token(tokens)
        _logger.debug(f'head token: {head_token} at {idx_head_token}')
        if head_token is None:
            return []

        pos_head_token = document.translate_index_to_position(head_token.index)
        last_token = tokens[-1]
        pos_cursor = document.translate_index_to_position(document.cursor_position)

        # Cursor is on a non-white token
        is_cursor_on_non_white_token = (last_token.index < document.cursor_position
                                        <= (last_token.index + len(last_token.value)))

        if head_token.ttype is ShellOut:
            _logger.debug('Completing for shell out')
            return _SYSTEM_COMPLETER.get_completions(Document(text[head_token.index + 1:]), complete_event)

        if is_cursor_on_non_white_token:
            _logger.debug(f'Cursor token: {last_token}')
            if last_token.ttype in (HttpMethod, FuncName):
                _logger.debug(f'Completing function/http method name: {last_token}')
                return itertools.chain(
                    _HTTP_METHOD_COMPLETER.get_completions(document, complete_event),
                    WordCompleter(['for', 'let']).get_completions(document, complete_event),
                    WordCompleter(self.app.vm.functions.keys()).get_completions(document, complete_event)
                )

            # The token right before cursor is HttpMethod, go for path completion
            if head_token.ttype is HttpMethod and idx_head_token == len(tokens) - 2 and last_token.ttype is Literal:
                return self._complete_http_path(document, complete_event, tokens[idx_head_token:])

            if head_token.value == 'run' and idx_head_token == len(tokens) - 2 and last_token.ttype in String:
                arg = text.split()[-1]
                if last_token.ttype in (String.Single, String.Double):
                    doc = Document(arg[1:])
                else:
                    doc = Document(arg[3:])
                _logger.debug(f'Completing for file path for run: {doc}')
                return _PATH_COMPLETER.get_completions(doc, complete_event)

            if head_token.ttype is HttpMethod:
                if last_token.ttype is At:
                    return _PATH_COMPLETER.get_completions(Document(text[last_token.index + 1:]), complete_event)
                elif last_token.ttype is Literal and len(tokens) > 1 and tokens[-2].ttype is At:
                    return _PATH_COMPLETER.get_completions(Document(last_token.value), complete_event)
                elif last_token.ttype is DictKey:
                    return self._complete_payload(document, complete_event, tokens[idx_head_token:])
            elif head_token.ttype is FuncName:
                if last_token.ttype in (At, Literal):
                    return self._complete_options(document, complete_event, tokens[idx_head_token:],
                                                  is_cursor_on_non_white_token)

            if last_token.ttype in (OptionName, Name):
                return self._complete_options(document, complete_event, tokens[idx_head_token:],
                                              is_cursor_on_non_white_token)

            return []

        else:  # Cursor is on a whitespace
            _logger.debug('cursor is after the last token')
            # Cursor is on whitespace after the last non-white token
            if pos_head_token[0] != pos_cursor[0] or last_token.ttype is HttpMethod:
                # Cursor is on separate line or immediately after http method
                return []
            else:
                # Cursor is on the same line and at the end of an ES API or func call
                _logger.debug('cursor is at the end of a statement')
                return self._complete_options(document, complete_event, tokens[idx_head_token:],
                                              is_cursor_on_non_white_token)

    def _complete_http_path(self, document: Document, complete_event: CompleteEvent, tokens) -> Iterable[Completion]:
        method_token, path_token = tokens[-2], tokens[-1]
        method = method_token.value.upper()
        cursor_position = document.cursor_position - path_token.index
        path = path_token.value[:cursor_position]
        _logger.debug(f'Completing http path: {path!r}')
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path))
        _logger.debug(f'path_tokens: {path_tokens}')
        if not path_tokens:  # empty, should not happen
            return []

        cursor_token = path_tokens[-1]
        _logger.debug(f'cursor_token: {cursor_token}')
        if cursor_token.ttype is Error:
            return []
        elif cursor_token.ttype in (PathPart, Slash):
            return self._complete_http_path_part(document, complete_event, method, path_tokens)
        elif cursor_token.ttype in (ParamName, QuestionMark, Ampersand):
            return self._complete_query_param_name(document, complete_event, method, path_tokens)
        else:  # skip for param value
            return self._complete_query_param_value(document, complete_event, method, path_tokens)

    def _complete_http_path_part(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
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

    def _complete_query_param_name(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        _logger.debug(f'Completing query param name: {path_tokens[-1]}')
        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_spec in matchable_specs(method, ts, self.specs):
            candidates.update(api_spec['url_params'].keys())

        return FuzzyCompleter(ConstantCompleter(
            [Completion(c, start_position=0) for c in candidates])).get_completions(document, complete_event)

    def _complete_query_param_value(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        _logger.debug(f'Completing query param value: {path_tokens[-1]}')
        param_name_token = path_tokens[-2] if path_tokens[-1].ttype is Assign else path_tokens[-3]
        _logger.debug(f'Param name token: {param_name_token}')
        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_spec in matchable_specs(method, ts, self.specs):
            v = api_spec['url_params'].get(param_name_token.value, None)
            if v is None:
                continue
            if v == '__flag__':
                candidates.update(('true', 'false'))
            elif isinstance(v, list) and len(v) > 0:
                candidates.update(v)

        return FuzzyCompleter(ConstantCompleter(
            [Completion(c, start_position=0) for c in candidates])).get_completions(document, complete_event)

    def _complete_options(self, document: Document, complete_event: CompleteEvent, tokens: List[PeekToken],
                          is_cursor_on_non_white_token):
        _logger.debug(f'Completing for options: {is_cursor_on_non_white_token}')
        head_token, last_token = tokens[0], tokens[-1]

        def _get_option_name_for_value_completion():
            if not is_cursor_on_non_white_token and last_token.ttype is Assign:
                return tokens[-2].value
            elif is_cursor_on_non_white_token and (len(tokens) > 1 and tokens[-2].ttype is Assign):
                return tokens[-3].value
            else:
                return None

        # TODO: For future handle the KeyName or Name is inside a function call, e.g. f(name=..)
        if head_token.ttype is HttpMethod:
            option_name = _get_option_name_for_value_completion()
            if option_name is not None:
                return []  # TODO: complete for value
            else:
                return _ES_API_CALL_OPTION_COMPLETER.get_completions(document, complete_event)
        elif head_token.ttype is FuncName:
            func = self.app.vm.functions.get(head_token.value)
            if func is None or not getattr(func, 'options', None):
                return []
            option_name = _get_option_name_for_value_completion()
            if option_name is not None:
                return []  # TODO: complete for value
            else:
                options = sorted([n if n.startswith('@') else (n + '=') for n in func.options.keys()])
                return WordCompleter(options, WORD=True).get_completions(
                    document, complete_event)
        else:
            return []

    def _complete_payload(self, document: Document, complete_event: CompleteEvent,
                          tokens: List[PeekToken]) -> Iterable[Completion]:
        _logger.debug(f'Completing for payload with tokens: {tokens}')
        method_token, path_token = tokens[0], tokens[1]
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path_token.value))
        ts = [t.value for t in path_tokens if t.ttype is not Slash]

        try:
            api_spec = next(matchable_specs(method_token.value.upper(), ts, self.specs,
                                            required_field='data_autocomplete_rules'))
        except StopIteration:
            return []

        rules = _maybe_unwrap_for_dict(api_spec.get('data_autocomplete_rules', None))
        if rules is None:
            return []

        _logger.debug(f'Found rules from spec: {rules}')

        payload_keys = []
        curly_level = 0
        for t in tokens[2:-1]:
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
                    raise PeekError(f'Error when counting curly level {curly_level} and keys {payload_keys}')

        _logger.debug(f'Payload status: level: {curly_level}, keys: {payload_keys}')
        if curly_level == 0:  # not even in the first curly bracket, no completion
            return []

        # Remove the payload key that is at the same level
        if curly_level == len(payload_keys):
            payload_keys.pop()

        for k in payload_keys:
            rules = _maybe_unwrap_for_dict(rules.get(k, None))
            if rules is None:
                _logger.debug(f'Rules not available for key: {k}')
                return []

        return FuzzyCompleter(ConstantCompleter(
            [Completion(c, start_position=0) for c in rules.keys()])).get_completions(document, complete_event)


def _maybe_unwrap_for_dict(rules):
    if isinstance(rules, dict):
        return rules
    elif isinstance(rules, list) and len(rules) > 0:
        if isinstance(rules[0], dict):
            return rules[0]
        else:
            return None
    else:
        return None


def find_beginning_token(tokens) -> Tuple[Optional[int], Optional[PeekToken]]:
    for i, t in zip(reversed(range(len(tokens))), tokens[::-1]):
        if t.ttype in (HttpMethod, FuncName, ShellOut):
            return i, t
    return None, None


def matchable_specs(method: str, ts: List[str], specs: Dict, required_field='url_params') -> Dict:
    """
    Find the matchable spec for the given HTTP method and input path.
    """
    for api_name, api_spec in specs.items():
        if method not in api_spec['methods']:
            continue
        if not api_spec.get(required_field, None):
            continue
        matched = False
        for pattern in api_spec['patterns']:
            ps = [p for p in pattern.split('/') if p]
            if len(ts) != len(ps):
                continue
            if not can_match(ts, ps):
                continue
            matched = True
            break
        if matched:
            yield api_spec


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


class ConstantCompleter(Completer):

    def __init__(self, candidates):
        self.candidates = candidates

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        return self.candidates


def load_specs(kibana_dir):
    oss_path = os.path.join(
        kibana_dir, 'src', 'plugins', 'console', 'server', 'lib', 'spec_definitions')
    xpack_path = os.path.join(
        kibana_dir, 'x-pack', 'plugins', 'console_extensions', 'server', 'lib', 'spec_definitions')
    specs = _load_json_specs(os.path.join(oss_path, 'json'))
    specs.update(_load_json_specs(os.path.join(xpack_path, 'json')))
    return specs


def _load_json_specs(base_dir):
    _logger.debug(f'Loading json specs from: {base_dir!r}')
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
