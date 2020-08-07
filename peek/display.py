import json
import logging
from json import JSONDecodeError

import pygments
from prompt_toolkit import print_formatted_text, HTML
from prompt_toolkit.formatted_text import PygmentsTokens, FormattedText
from prompt_toolkit.styles import style_from_pygments_cls

from peek.lexers import PeekStyle, PeekLexer, Heading

_logger = logging.getLogger(__name__)

OUTPUT_HEADER = FormattedText([(PeekStyle.styles[Heading], '===')])
ERROR_HEADER = HTML('<ansired>---</ansired>')


class Display:

    def __init__(self, app):
        self.app = app
        self.payload_lexer = PeekLexer(stack=('dict',))

    @property
    def pretty_print(self):
        return self.app.config.as_bool('pretty_print')

    def info(self, source, header=True):
        if source is None:
            return
        if header and not self.app.batch_mode:
            print_formatted_text(OUTPUT_HEADER)
        if self._try_json(source):
            return
        # TODO: try more types
        print_formatted_text(source)

    def error(self, source, header=True):
        if source is None:
            return
        if header and not self.app.batch_mode:
            print_formatted_text(ERROR_HEADER)
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
            tokens = list(pygments.lex(source, lexer=self.payload_lexer))
            print_formatted_text(PygmentsTokens(tokens), style=style_from_pygments_cls(PeekStyle))
            return True
        except Exception as e:
            _logger.debug(f'Cannot render object as json: {source!r}, {e}')
            return False
