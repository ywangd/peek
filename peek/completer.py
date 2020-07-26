import json
import logging
import os
from typing import Iterable

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter
from prompt_toolkit.document import Document
from pygments.lexer import Lexer
from pygments.token import Whitespace, Comment, Token

from peek.lexers import Percent

_logger = logging.getLogger(__name__)

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)


class PeekCompleter(Completer):

    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.specs = load_rest_api_spec()

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        text = document.text[:document.cursor_position]
        _logger.debug(f'text: {repr(text)}')

        # Merge consecutive error tokens
        tokens = []
        error_token = None
        for token in self.lexer.get_tokens_unprocessed(text):
            if token[1] in (Whitespace, Comment.Single):
                if error_token is not None:
                    tokens.append(error_token)
                    error_token = None
            elif token[1] is Token.Error:
                error_token = token if error_token is None else (
                    error_token[0], error_token[1], error_token[2] + token[2])
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

        elif len(tokens) == 1 and tokens[0] == Percent:
            return self._complete_special(document, complete_event)

        elif len(tokens) == 1 and (tokens[0][0] + len(tokens[0][2]) >= document.cursor_position):
            return _HTTP_METHOD_COMPLETER.get_completions(document, complete_event)

        elif len(tokens) == 2:
            return self._complete_path(tokens, document, complete_event)

        else:
            return self._complete_payload(document, complete_event)

    def _complete_path(self, tokens, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        method_token, path_token = tokens
        # If there are whitespaces after path, provide no completion
        if path_token[0] + len(path_token[2]) < document.cursor_position:
            return []
        method = method_token[2].upper()
        path = path_token[2]
        ret = []
        # TODO: handle placeholder in path
        # TODO: complete parameters
        for name, spec in self.specs.items():
            for p in spec['url']['paths']:
                if method in p['methods']:
                    if p['path'].startswith(path) or p['path'].startswith(f'/{path}'):
                        ret.append(Completion(p['path'], start_position=-len(path)))
        return ret

    def _complete_payload(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        # TODO: payload completion
        return []

    def _complete_special(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        # TODO: special command completion
        return []


def load_rest_api_spec():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    spec_dir = os.path.join(package_root, 'rest-api-spec', 'api')
    spec_files = [f for f in os.listdir(spec_dir) if f.endswith('.json')]
    specs = {}
    for spec_file in spec_files:
        if spec_file == '_common.json':
            continue
        with open(os.path.join(spec_dir, spec_file)) as ins:
            specs.update(json.load(ins))
    return specs
