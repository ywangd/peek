import json
import logging
from json import JSONDecodeError

import pygments
from peek.lexers import PayloadLexer, PeekStyle
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import PygmentsTokens
from prompt_toolkit.styles import style_from_pygments_cls

_logger = logging.getLogger(__name__)


class Display:

    def __init__(self, app):
        self.app = app

    @property
    def pretty_print(self):
        return self.app.config.as_bool('pretty_print')

    def show(self, source):
        if source is None:
            return
        if self._try_json(source):
            return
        # TODO: try more types
        print_formatted_text(source)

    def _try_json(self, source):
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except JSONDecodeError as e:
                _logger.debug(f'Cannot decode string to json: {source!r} {e}')
                return False
        try:
            source = json.dumps(source, indent=2 if self.pretty_print else None)
            tokens = list(pygments.lex(source, lexer=PayloadLexer()))
            print_formatted_text(PygmentsTokens(tokens), style=style_from_pygments_cls(PeekStyle))
            return True
        except Exception as e:
            _logger.debug(f'Cannot render object as json: {source!r}, {e}')
            return False
