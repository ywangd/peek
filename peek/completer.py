import json
import logging
import os
from typing import Iterable

from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from pygments.token import Whitespace, Comment, Token, Keyword

from peek.lexers import Percent, PeekLexer, Variable

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)

_FUNC_NAME_COMPLETER = WordCompleter(['connect', 'connections'])


class PeekCompleter(Completer):

    def __init__(self):
        self.lexer = PeekLexer()
        self.specs = load_rest_api_spec()

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        _logger.debug(f'doc: {document}, event: {complete_event}')

        text = document.text[:document.cursor_position]
        _logger.debug(f'text: {repr(text)}')

        # Merge consecutive error tokens
        tokens = []
        error_token = None
        for token in self.lexer.get_tokens_unprocessed(text):
            if token.ttype in (Whitespace, Comment.Single):
                if error_token is not None:
                    tokens.append(error_token)
                    error_token = None
            elif token.ttype is Token.Error:
                error_token = token if error_token is None else (
                    error_token.index, error_token.ttype, error_token.value + token.value)
            else:
                if error_token is not None:
                    tokens.append(error_token)
                    error_token = None
                tokens.append(token)
        if error_token is not None:
            tokens.append(error_token)
        _logger.debug(f'tokens: {tokens}')

        if len(tokens) == 0:
            return []

        elif len(tokens) == 1 and tokens[0].ttype is Variable and \
            tokens[0].index + len(tokens[0].value) >= document.cursor_position:
            return self._complete_func_call(document, complete_event)

        elif len(tokens) == 1 and tokens[0].ttype is Keyword and \
            tokens[0].index + len(tokens[0].value) >= document.cursor_position:
            _logger.debug('HTTP method completing')
            return _HTTP_METHOD_COMPLETER.get_completions(document, complete_event)

        elif len(tokens) == 2 or (
            len(tokens) == 1 and get_app().layout.get_buffer_by_name(DEFAULT_BUFFER).document.cursor_position > document.cursor_position):
            return self._complete_path(tokens, document, complete_event)

        else:
            return self._complete_payload(document, complete_event)

    def _complete_path(self, tokens, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        method_token, path_token = tokens
        # If there are whitespaces after path, provide no completion
        if path_token.index + len(path_token.value) < document.cursor_position:
            return []
        method = method_token.value.upper()
        path = path_token.value
        _logger.debug(f'Path completing: {repr(path)}')
        ret = []
        # TODO: handle placeholder in path
        # TODO: complete parameters
        for name, spec in self.specs.items():
            for p in spec['url']['paths']:
                if method in p['methods']:
                    if p['path'].startswith(path) or p['path'].startswith('/' + path):
                        ret.append(Completion(p['path'], start_position=-len(path)))
        return ret

    def _complete_payload(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        # TODO: payload completion
        return []

    def _complete_func_call(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        # TODO: function call completion
        return _FUNC_NAME_COMPLETER.get_completions(document, complete_event)


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
