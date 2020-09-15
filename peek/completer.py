import itertools
import logging
import os
from enum import Enum
from typing import Iterable, List, Tuple, Optional

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter, FuzzyCompleter, PathCompleter
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.document import Document
from pygments.token import Error, Name, Literal, String

from peek.common import PeekToken
from peek.completions import PayloadKeyCompletion
from peek.es_api_spec.spec import ApiSpec
from peek.lexers import PeekLexer, UrlPathLexer, PathPart, ParamName, Ampersand, QuestionMark, Slash, HttpMethod, \
    FuncName, OptionName, Assign, DictKey, ShellOut, At, Let, For
from peek.parser import process_tokens, PeekParser, ParserEvent, ParserEventType

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)

_ES_API_CALL_OPTION_COMPLETER = WordCompleter([w + '=' for w in sorted(['conn', 'runas', 'headers', 'xoid', 'quiet'])])

_PATH_COMPLETER = PathCompleter(expanduser=True)
_SYSTEM_COMPLETER = SystemCompleter()


class CompletionCategory(Enum):
    BEGIN_OF_STMT = 'BEGIN_OF_STMT'


class CompletionDecider:

    def __init__(self, text: str):
        self.text = text
        self._events = []
        self._tokens: List[PeekToken] = []
        self._stmt_token = None
        self.state = None

    def __call__(self, event: ParserEvent):
        self._events.append(event)
        if event.type is ParserEventType.AFTER_TOKEN:
            self._tokens.append(event.token)

    @property
    def stmt_token(self):
        return self._stmt_token

    @property
    def tokens(self):
        return self._tokens

    @property
    def is_completion_possible(self):
        if self._stmt_token is None or not self._tokens:
            return False
        last_token = self.tokens[-1]
        if self.text[last_token.index:].rstrip() == last_token.value:
            return True
        else:
            return False

    def completion_category(self):
        """
        * Stmt token
        * HTTP URL path
        * HTTP query Param Name
        * HTTP query Param Value
        * HTTP option name
        * HTTP option value
        * HTTP payload key
        * HTTP payload value
        * Function option name
        * Function option value
        * Function symbol arg
        * Shell out path
        * Run function path
        """
        cursor_on_white = self.text[-1] == ' '
        if cursor_on_white:
            pass
        else:
            if len(self._tokens) == 1 and self._tokens[0].ttype is not ShellOut:
                pass



    def _handle_event(self, event: ParserEvent):
        if event is ParserEventType.BEFORE_ES_METHOD:
            self.state = 'es_api_stmt'
        elif event is ParserEventType.BEFORE_FUNC_STMT:
            self.state = 'func_stmt'
        elif event is ParserEventType.BEFORE_LET:
            self.state = 'let_stmt'
        elif event is ParserEventType.BEFORE_FOR:
            self.state = 'for_stmt'
        elif event is ParserEventType.BEFORE_SHELL_OUT:
            self.state = 'shell_out_stmt'
        elif event is ParserEventType.BEFORE_ES_URL:
            self.state = 'es_url'
        elif event is ParserEventType.BEFORE_ES_OPTION_NAME:
            self.state = 'es_option_name'
        elif event is ParserEventType.BEFORE_ES_OPTION_VALUE:
            self.state = 'es_option_value'



class PeekCompleter(Completer):

    def __init__(self, app):
        self.app = app
        self.lexer = PeekLexer()
        self.url_path_lexer = UrlPathLexer()
        from peek import __file__ as package_root
        package_root = os.path.dirname(package_root)
        kibana_dir = app.config['kibana_dir'] or os.path.join(package_root, 'specs', 'kibana-7.8.1')
        self.api_spec = ApiSpec(app, kibana_dir)

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        _logger.debug(f'Document: {document}, Event: {complete_event}')

        text_before_cursor = document.text_before_cursor
        _logger.debug(f'Text before cursor: {text_before_cursor!r}')
        if text_before_cursor.strip() == '':
            return []

        decider = CompletionDecider(text_before_cursor)
        try:
            PeekParser((decider,)).parse(text_before_cursor,
                                         fail_fast_on_error_token=False,
                                         last_stmt_only=True,
                                         log_level='WARNING')
        except Exception:
            pass

        if not decider.is_completion_possible:
            return []

        cursor_on_white = text_before_cursor[-1] == ' '

        if cursor_on_white:
            pass
        else:
            pass




        pos_head_token = document.translate_index_to_position(head_token.index)
        last_token = tokens[-1]
        pos_cursor = document.translate_index_to_position(document.cursor_position)

        # Cursor is on a non-white token
        is_cursor_on_non_white_token = (last_token.index < document.cursor_position
                                        <= (last_token.index + len(last_token.value)))

        if head_token.ttype is ShellOut:
            _logger.debug('Completing for shell out')
            return _SYSTEM_COMPLETER.get_completions(
                Document(text_before_cursor[head_token.index + 1:]), complete_event)

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
                arg = text_before_cursor.split()[-1]
                if last_token.ttype in (String.Single, String.Double):
                    doc = Document(arg[1:])
                else:
                    doc = Document(arg[3:])
                _logger.debug(f'Completing for file path for run: {doc}')
                return _PATH_COMPLETER.get_completions(doc, complete_event)

            if head_token.ttype is HttpMethod:
                if last_token.ttype is At:
                    return _PATH_COMPLETER.get_completions(
                        Document(text_before_cursor[last_token.index + 1:]), complete_event)
                elif last_token.ttype is Literal and len(tokens) > 1 and tokens[-2].ttype is At:
                    return _PATH_COMPLETER.get_completions(Document(last_token.value), complete_event)
                elif last_token.ttype is DictKey:
                    return self._complete_payload(document, complete_event, tokens[idx_head_token:])
                elif last_token.ttype in (OptionName, Name) and '\n' not in text_before_cursor[head_token.index:]:
                    return self._complete_options(document, complete_event, tokens[idx_head_token:],
                                                  is_cursor_on_non_white_token)
            elif head_token.ttype is FuncName:
                if last_token.ttype in (At, Literal):
                    return self._complete_options(document, complete_event, tokens[idx_head_token:],
                                                  is_cursor_on_non_white_token)
                elif last_token.ttype in (OptionName, Name):
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
        _logger.debug(f'Completing HTTP API url: {path!r}')
        path_tokens = list(self.url_path_lexer.get_tokens_unprocessed(path))
        _logger.debug(f'path_tokens: {path_tokens}')
        if not path_tokens:  # empty, should not happen
            return []

        cursor_token = path_tokens[-1]
        _logger.debug(f'cursor_token: {cursor_token}')
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
        effective_text = document.text_before_cursor[method_token.index:]
        idx_nl = effective_text.find('\n')
        # If there is no newline, it is definitely an option value
        if idx_nl == -1:
            return []
        # TODO: it is still possible that an option value is multi-line, e.g. headers.
        #       Theoretically, it also be function call

        # TODO: this is not correct since there maybe options after the first 2 tokens
        #       In fact, there is no way to tell for sure where the payload begins without
        #       parse the token stream
        payload_tokens = tokens[2:]
        candidates, rules = self.api_spec.complete_payload(
            document, complete_event, method_token.value.upper(), path_tokens, payload_tokens)
        if not candidates:
            return []
        constant_completer = ConstantCompleter(candidates)
        for c in FuzzyCompleter(constant_completer).get_completions(document, complete_event):
            yield PayloadKeyCompletion(c.text, rules[c.text],
                                       c.start_position, c.display, c.display_meta, c.style, c.selected_style)


def find_head_token(tokens) -> Tuple[Optional[int], Optional[PeekToken]]:
    """
    Find the last token that can start a statement
    """
    for i, t in zip(reversed(range(len(tokens))), tokens[::-1]):
        if t.ttype in (HttpMethod, FuncName, ShellOut, Let, For):
            return i, t
    return None, None


class ConstantCompleter(Completer):

    def __init__(self, candidates):
        self.candidates = candidates

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        return self.candidates
