import json
import logging
import sys
from json import JSONDecodeError
from typing import Any

import pygments
from prompt_toolkit import print_formatted_text, HTML
from prompt_toolkit.formatted_text import PygmentsTokens, FormattedText, to_formatted_text, merge_formatted_text
from prompt_toolkit.styles import style_from_pygments_cls, ConditionalStyleTransformation, \
    SwapLightAndDarkStyleTransformation
from pygments.token import Token

from peek.lexers import PeekStyle, PeekLexer, Heading, TipsMinor

_logger = logging.getLogger(__name__)


class Display:

    def __init__(self, app):
        self.app = app
        self.payload_lexer = PeekLexer(stack=('value',))
        self.style = style_from_pygments_cls(PeekStyle)
        self.style_transformation = ConditionalStyleTransformation(
            SwapLightAndDarkStyleTransformation(), self.app.config.as_bool('swap_colour'))

    @property
    def pretty_print(self):
        return self.app.config.as_bool('pretty_print')

    def info(self, source, header_text=''):
        if source is None:
            return
        if not self.app.batch_mode:
            self._tee_print(
                FormattedText([
                    (PeekStyle.styles[Heading], '=== '),
                    (PeekStyle.styles[TipsMinor], header_text)
                ]),
                plain_source=f'=== {header_text}')
        if isinstance(source, FormattedText):
            self._tee_print(source)
        else:
            source, plain_source = self._try_jsonify(source)  # TODO: try more types
            self._tee_print(source, plain_source=plain_source)

    def error(self, source, header_text=''):
        if source is None:
            return
        if not self.app.batch_mode:
            self._tee_print(
                merge_formatted_text([
                    HTML('<ansired>--- </ansired>').formatted_text,
                    FormattedText([(PeekStyle.styles[TipsMinor], header_text)])
                ]),
                plain_source=f'--- {header_text}')
        if isinstance(source, FormattedText):
            self._tee_print(source)
        else:
            self._tee_print(source, plain_source=source)

    def warn(self, source):
        if source is None:
            return
        if isinstance(source, FormattedText):
            self._tee_print(source)
        else:
            self._tee_print(
                FormattedText([
                    ('#ffdf5d', f'WARNING: {source}'),
                ]),
                plain_source=f'WARNING: {source}')

    def _try_jsonify(self, source):
        # If it is a string, first check whether it can be decoded as JSON
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except JSONDecodeError:
                _logger.debug(f'Source string is not JSON: {source!r}')

        try:
            if not isinstance(source, str):
                source = json.dumps(
                    source,
                    cls=PeekEncoder,
                    app=self.app,
                    indent=2 if self.pretty_print else None)
            tokens = []
            for t in pygments.lex(source, lexer=self.payload_lexer):
                tokens.append(t)
                if t[0] is Token.Error:
                    _logger.debug(f'Source string is not valid payload type: {t!r}')
                    return source, source
            return PygmentsTokens(tokens), source
        except Exception as e:
            _logger.debug(f'Cannot render object as json: {source!r}, {e}')
            return source, source

    def _tee_print(self, source, plain_source=None):
        content = None
        if self.app.batch_mode and not sys.stdout.isatty():
            content = all_to_text(source) if plain_source is None else plain_source
            print(content, file=sys.stdout, end='')
        else:
            print_formatted_text(source, style=self.style, style_transformation=self.style_transformation)

        if self.app.capture.file() is not None:
            content = content or (all_to_text(source) if plain_source is None else plain_source)
            print(content, file=self.app.capture.file())


class PeekEncoder(json.JSONEncoder):

    def __init__(self, app=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        assert self.app is not None, 'Parameter app must be provided'

    def default(self, o: Any) -> Any:
        if self.app is not None and callable(o):
            function_lookup = {v: k for k, v in self.app.vm.functions.items()}
            if o in function_lookup:
                return f'<PeekFunction {function_lookup[o]}>'
        return str(o)


def all_to_text(*args):
    fragments = []
    for v in args:
        fragments.extend(to_text(v))
    return ''.join([v[1] for v in fragments])


def to_text(val):
    # Normal lists which are not instances of `FormattedText` are
    # considered plain text.
    if isinstance(val, list) and not isinstance(val, FormattedText):
        return to_formatted_text("{0}".format(val))
    return to_formatted_text(val, auto_convert=True)
