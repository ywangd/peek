import json
import logging
from json import JSONDecodeError

import pygments
from prompt_toolkit import print_formatted_text, HTML
from prompt_toolkit.formatted_text import PygmentsTokens, FormattedText, to_formatted_text
from prompt_toolkit.styles import style_from_pygments_cls, ConditionalStyleTransformation, \
    SwapLightAndDarkStyleTransformation

from peek.lexers import PeekStyle, PeekLexer, Heading, TipsMinor

_logger = logging.getLogger(__name__)


class Display:

    def __init__(self, app):
        self.app = app
        self.payload_lexer = PeekLexer(stack=('value',))
        self.style_transformation = ConditionalStyleTransformation(
            SwapLightAndDarkStyleTransformation(), self.app.config.as_bool('swap_colour'))

    @property
    def pretty_print(self):
        return self.app.config.as_bool('pretty_print')

    def info(self, source, header_text=''):
        if source is None:
            return
        if not self.app.batch_mode:
            self.tee_print(FormattedText([
                (PeekStyle.styles[Heading], '=== '),
                (PeekStyle.styles[TipsMinor], header_text)
            ]), style_transformation=self.style_transformation)
        if self._try_json(source):
            return
        # TODO: try more types
        self.tee_print(source, style_transformation=self.style_transformation)

    def error(self, source, header_text=''):
        if source is None:
            return
        if not self.app.batch_mode:
            self.tee_print(
                HTML('<ansired>--- </ansired>'),
                FormattedText([(PeekStyle.styles[TipsMinor], header_text)]),
                style_transformation=self.style_transformation)
        self.tee_print(source, style_transformation=self.style_transformation)

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
            self.tee_print(PygmentsTokens(tokens), style=style_from_pygments_cls(PeekStyle),
                           style_transformation=self.style_transformation)
            return True
        except Exception as e:
            _logger.debug(f'Cannot render object as json: {source!r}, {e}')
            return False

    def tee_print(self, *args, **kwargs):
        print_formatted_text(*args, **kwargs)
        if self.app.capture.file() is not None:
            fragments = []
            for v in args:
                fragments.extend(to_text(v))
            print(''.join([v[1] for v in fragments]), file=self.app.capture.file())


def to_text(val):
    # Normal lists which are not instances of `FormattedText` are
    # considered plain text.
    if isinstance(val, list) and not isinstance(val, FormattedText):
        return to_formatted_text("{0}".format(val))
    return to_formatted_text(val, auto_convert=True)
