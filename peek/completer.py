import itertools
import logging
import os
from typing import Iterable, List, Optional

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter, FuzzyCompleter, PathCompleter
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.document import Document
from pygments.token import Error, Literal, String, Name

from peek.common import PeekToken, HTTP_METHODS
from peek.completions import PayloadKeyCompletion
from peek.config import config_location
from peek.es_api_spec.spec import ApiSpec
from peek.lexers import PeekLexer, UrlPathLexer, PathPart, ParamName, Ampersand, QuestionMark, Slash, HttpMethod, \
    FuncName, ShellOut, DictKey, EOF
from peek.parser import PeekParser, ParserEvent, ParserEventType

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter([m.upper() for m in HTTP_METHODS], ignore_case=True)

_ES_API_CALL_OPTION_NAME_COMPLETER = WordCompleter(
    [w + '=' for w in sorted(['conn', 'runas', 'headers', 'xoid', 'quiet'])])

_PATH_COMPLETER = PathCompleter(expanduser=True)
_SYSTEM_COMPLETER = SystemCompleter()

_DICT_EVENT_TYPES = (
    ParserEventType.DICT_KEY,
    ParserEventType.BEFORE_DICT_KEY_EXPR, ParserEventType.AFTER_DICT_KEY_EXPR,
    ParserEventType.BEFORE_DICT_VALUE, ParserEventType.AFTER_DICT_VALUE,
)


class ParserStateTracker:

    def __init__(self, text: str):
        self.text = text
        self._events: List[ParserEvent] = []
        self._tokens: List[PeekToken] = []
        self._payload_events: List[ParserEvent] = []

    def __call__(self, event: ParserEvent):
        if event.type is ParserEventType.AFTER_TOKEN:
            self._tokens.append(event.token)
        elif event.type in _DICT_EVENT_TYPES:

            if self.last_event.type is ParserEventType.BEFORE_ES_PAYLOAD_INLINE:
                self._payload_events.append(event)
            else:
                _logger.debug(f'Ignore dict parsing events for non-payload: {self.last_event}')
        else:
            self._events.append(event)
            if event is ParserEventType.BEFORE_ES_PAYLOAD_INLINE:
                self._payload_events = []

    @property
    def events(self):
        return self._events

    @property
    def tokens(self):
        return self._tokens

    @property
    def payload_events(self):
        return self._payload_events

    @property
    def stmt_token(self) -> Optional[PeekToken]:
        if not self._events:
            return None
        return self._events[0].token

    @property
    def is_completion_possible(self):
        if self.stmt_token is None or not self._tokens:
            return False
        # The last non-white char must be parsed successfully for completion to be available
        last_token = self.last_token
        if last_token is None:
            return False
        if self.text[last_token.index:].rstrip() == last_token.value:
            return True
        else:
            return False

    @property
    def last_token(self) -> Optional[PeekToken]:
        if not self._tokens:
            return None
        return self._tokens[-1]

    @property
    def last_event(self) -> Optional[ParserEvent]:
        if not self._events:
            return None
        return self._events[-1]

    @property
    def last_payload_event(self) -> Optional[ParserEvent]:
        if not self._payload_events:
            return None
        return self._payload_events[-1]

    @property
    def is_cursor_on_whitespace(self):
        last_token = self.last_token
        if last_token is None:
            return True
        return len(self.text) > (last_token.index + len(last_token.value))

    @property
    def is_within_payload_value(self):
        last_payload_event = self.last_payload_event
        if last_payload_event is None:
            return False
        return last_payload_event.type is ParserEventType.BEFORE_DICT_VALUE or (
            last_payload_event.type is ParserEventType.AFTER_DICT_VALUE and last_payload_event.token.ttype is EOF)

    @property
    def has_newline_after_last_token(self):
        last_token = self.tokens[-1]
        return '\n' in self.text[last_token.index:]


class PeekCompleter(Completer):

    def __init__(self, app):
        self.app = app
        self.lexer = PeekLexer()
        self.url_path_lexer = UrlPathLexer()
        self.api_spec = self.init_api_specs()

    def init_api_specs(self):
        from peek import __file__ as package_root
        package_root = os.path.dirname(package_root)
        kibana_dir = self.app.config['kibana_dir']
        if not kibana_dir:
            config_dir = config_location()
            if os.path.exists(config_dir):
                kibana_dirs = [os.path.join(config_dir, d) for d in os.listdir(config_dir) if d.startswith('kibana-')]
                if kibana_dirs:
                    kibana_dir = kibana_dirs[0]
        if not kibana_dir:
            kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')
        _logger.info(f'Attempt to build Elasticsearch API specs from: {kibana_dir}')
        return ApiSpec(self.app, kibana_dir)

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        _logger.debug(f'Document: {document}, Event: {complete_event}')

        text_before_cursor = document.text_before_cursor
        _logger.debug(f'Text before cursor: {text_before_cursor!r}')
        if text_before_cursor.strip() == '':
            return []

        state_tracker = ParserStateTracker(text_before_cursor)
        try:
            PeekParser((state_tracker,)).parse(text_before_cursor,
                                               fail_fast_on_error_token=True,
                                               last_stmt_only=True,
                                               log_level='WARNING')
        except Exception:
            pass

        if not state_tracker.is_completion_possible:
            _logger.debug('No completion is available according to state_tracker')
            return []

        stmt_token = state_tracker.stmt_token
        if stmt_token.ttype is ShellOut:
            _logger.debug('Completing for shell out')
            return _SYSTEM_COMPLETER.get_completions(
                Document(text_before_cursor[stmt_token.index + 1:]), complete_event)

        if state_tracker.is_cursor_on_whitespace:
            return self._get_completions_for_whitespace(document, complete_event, state_tracker)

        else:
            return self._get_completions_for_non_white(document, complete_event, state_tracker)

    def _get_completions_for_whitespace(self, document: Document, complete_event: CompleteEvent,
                                        state_tracker: ParserStateTracker) -> Iterable[Completion]:
        _logger.debug('Cursor is on a whitespace')
        stmt_token = state_tracker.stmt_token
        last_token = state_tracker.last_token
        last_event = state_tracker.last_event
        _logger.debug(f'Last Event: {last_event}, Last Token: {last_token}')
        has_newline_after_last_token = state_tracker.has_newline_after_last_token

        # Only option name/value completions are available when cursor is on whitespace char
        if stmt_token.ttype is HttpMethod and not has_newline_after_last_token:
            if last_event.type in (ParserEventType.ES_URL,
                                   ParserEventType.AFTER_ES_URL_EXPR,
                                   ParserEventType.AFTER_ES_OPTION_VALUE):
                return _ES_API_CALL_OPTION_NAME_COMPLETER.get_completions(document, complete_event)
            elif last_event.type is ParserEventType.BEFORE_ES_OPTION_VALUE:
                return []  # TODO: ES option value
            elif last_event.type is ParserEventType.BEFORE_ES_PAYLOAD_INLINE:
                if state_tracker.last_payload_event.type is ParserEventType.BEFORE_DICT_VALUE:
                    return self._maybe_complete_payload_value(document, complete_event, state_tracker)

        elif stmt_token.ttype is FuncName and not has_newline_after_last_token:
            if last_event.type in (ParserEventType.FUNC_STMT, ParserEventType.AFTER_FUNC_ARGS):
                return self._maybe_complete_func_option_name(document, complete_event, state_tracker)
            elif last_event.type is ParserEventType.BEFORE_FUNC_OPTION_VALUE:
                return []  # TODO: Func option value
        else:
            return []  # TODO: Options of func expr

        return []

    def _get_completions_for_non_white(self, document: Document, complete_event: CompleteEvent,
                                       state_tracker: ParserStateTracker) -> Iterable[Completion]:
        _logger.debug('Cursor is on an non-white char')
        stmt_token = state_tracker.stmt_token
        last_token = state_tracker.last_token
        last_event = state_tracker.last_event
        _logger.debug(f'Last Event: {last_event}, Last Token: {last_token}')

        if len(state_tracker.tokens) == 1:
            _logger.debug(f'Completing for beginning of stmt: {stmt_token}')
            return itertools.chain(
                _HTTP_METHOD_COMPLETER.get_completions(document, complete_event),
                WordCompleter(['for', 'let']).get_completions(document, complete_event),
                WordCompleter(self.app.vm.functions.keys()).get_completions(document, complete_event)
            )

        elif stmt_token.ttype is HttpMethod:
            if last_event.type is ParserEventType.ES_URL:
                # ES_URL not ES_METHOD because we do not provide completion for empty string
                return self._maybe_complete_http_path(document, complete_event, state_tracker)
            elif last_event.type is ParserEventType.ES_OPTION_NAME:
                return _ES_API_CALL_OPTION_NAME_COMPLETER.get_completions(document, complete_event)
            elif last_event.type is ParserEventType.BEFORE_ES_OPTION_VALUE:
                return []  # TODO: ES option value
            elif last_event.type is ParserEventType.ES_PAYLOAD_FILE_AT:
                return _PATH_COMPLETER.get_completions(
                    Document(state_tracker.text[last_event.token.index + 1:]), complete_event)
            elif last_event.type is ParserEventType.BEFORE_ES_PAYLOAD_INLINE:
                _logger.debug(f'Last payload event: {state_tracker.last_payload_event}')
                if last_token.ttype is DictKey:
                    return self._maybe_complete_payload(document, complete_event, state_tracker)
                elif state_tracker.is_within_payload_value:
                    return self._maybe_complete_payload_value(document, complete_event, state_tracker)

        elif stmt_token.ttype is FuncName:
            if self._function_option_name_can_appear(last_event, last_token):
                return self._maybe_complete_func_option_name(document, complete_event, state_tracker)
            elif last_event.type is ParserEventType.BEFORE_FUNC_OPTION_VALUE:
                return []  # TODO: Function option value
            elif stmt_token.value == 'run':
                return self._maybe_complete_special_for_run_func_file_path(document, complete_event, state_tracker)

        else:
            return []  # TODO: func expr

        return []

    def _function_option_name_can_appear(self, last_event: ParserEvent, last_token: PeekToken) -> bool:
        return (last_event.type is ParserEventType.AFTER_FUNC_ARGS and last_token.ttype in (Literal, Name)) \
               or last_event.type is ParserEventType.BEFORE_FUNC_SYMBOL_ARG

    def _maybe_complete_func_option_name(self, document: Document, complete_event: CompleteEvent,
                                         state_tracker: ParserStateTracker) -> Iterable[Completion]:
        stmt_token = state_tracker.stmt_token
        func = self.app.vm.functions.get(stmt_token.value)
        if func is None or not getattr(func, 'options', None):
            return []
        options = sorted([n if n.startswith('@') else (n + '=') for n in func.options.keys()])
        return WordCompleter(options, WORD=True).get_completions(document, complete_event)

    def _maybe_complete_special_for_run_func_file_path(self, document: Document, complete_event: CompleteEvent,
                                                       state_tracker: ParserStateTracker):
        if len(state_tracker.tokens) == 2 and state_tracker.tokens[-1].ttype in String:
            last_token = state_tracker.last_token
            if last_token.ttype in (String.Single, String.Double):
                doc = Document(last_token.value[1:])
            else:
                doc = Document(last_token.value[3:])
            _logger.debug(f'Completing for file path for run: {doc}')
            return _PATH_COMPLETER.get_completions(doc, complete_event)
        else:
            return []

    def _maybe_complete_http_path(self, document: Document, complete_event: CompleteEvent,
                                  state_tracker: ParserStateTracker) -> Iterable[Completion]:
        tokens = state_tracker.tokens
        method_token, path_token = tokens[-2], tokens[-1]
        method = method_token.value.upper()
        cursor_position = document.cursor_position - path_token.index
        path = path_token.value[:cursor_position]
        _logger.debug(f'Completing HTTP API url: {path!r}')
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path))
        _logger.debug(f'URL Path Tokens: {path_tokens}')
        if not path_tokens:  # empty, should not happen
            return []

        cursor_token = path_tokens[-1]
        _logger.debug(f'Cursor Token: {cursor_token}')
        if cursor_token.ttype is Error:
            return []
        else:
            if cursor_token.ttype in (PathPart, Slash):
                complete_func = self.api_spec.complete_url_path
            elif cursor_token.ttype in (ParamName, QuestionMark, Ampersand):
                complete_func = self.api_spec.complete_query_param_name
            else:
                complete_func = self.api_spec.complete_query_param_value
            candidates = complete_func(document, complete_event, method, path_tokens)
            return FuzzyCompleter(ConstantCompleter(candidates)).get_completions(document, complete_event)

    def _maybe_complete_payload(self, document: Document, complete_event: CompleteEvent,
                                state_tracker: ParserStateTracker) -> Iterable[Completion]:
        tokens = state_tracker.tokens
        _logger.debug(f'Completing for payload with tokens: {tokens}')
        path_event = state_tracker.events[1]
        if path_event.token.ttype is not Literal:  # No completion for non-literal URL
            return []
        method_token, path_token = tokens[0], tokens[1]
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path_token.value))
        last_event = state_tracker.last_event
        payload_tokens = tokens[tokens.index(last_event.token):]
        candidates, rules = self.api_spec.complete_payload(
            document, complete_event, method_token.value.upper(), path_tokens, payload_tokens)
        if not candidates:
            return []
        constant_completer = ConstantCompleter(candidates)
        for c in FuzzyCompleter(constant_completer).get_completions(document, complete_event):
            yield PayloadKeyCompletion(c.text, rules[c.text],
                                       c.start_position, c.display, c.display_meta, c.style, c.selected_style)

    def _maybe_complete_payload_value(self, document: Document, complete_event: CompleteEvent,
                                      state_tracker: ParserStateTracker) -> Iterable[Completion]:
        tokens = state_tracker.tokens
        _logger.debug(f'Completing for payload value with tokens: {tokens}')
        path_event = state_tracker.events[1]
        if path_event.token.ttype is not Literal:  # No completion for non-literal URL
            return []
        method_token, path_token = tokens[0], tokens[1]
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path_token.value))
        last_event = state_tracker.last_event
        candidates, rules = self.api_spec.complete_payload_value(
            document, complete_event, method_token.value.upper(), path_tokens,
            tokens[tokens.index(last_event.token):], state_tracker.payload_events
        )
        if not candidates:
            return []
        constant_completer = ConstantCompleter(candidates)
        return FuzzyCompleter(constant_completer).get_completions(document, complete_event)


class ConstantCompleter(Completer):

    def __init__(self, candidates):
        self.candidates = candidates

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        return self.candidates
