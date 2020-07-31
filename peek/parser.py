import ast
import json
import logging
from abc import ABCMeta, abstractmethod
from typing import List, NamedTuple, Iterable

from pygments.token import Token, Whitespace, String, Comment, Literal, Keyword, Number, Name, _TokenType

from peek.errors import PeekSyntaxError
from peek.lexers import PeekLexer, BlankLine, Percent, SpecialFunc, HTTP_METHODS, CurlyLeft, PayloadKey, Colon, \
    CurlyRight, Comma, BracketLeft, BracketRight, TripleS, TripleD, EOF

_logger = logging.getLogger(__name__)

PeekToken = NamedTuple('PeekToken', [('index', int), ('ttype', _TokenType), ('value', str)])


class Stmt(metaclass=ABCMeta):

    @abstractmethod
    def execute(self, vm):
        pass

    @abstractmethod
    def format_compact(self):
        pass

    @abstractmethod
    def format_pretty(self):
        pass

    def __repr__(self):
        return str(self)


class SpecialStmt(Stmt):

    def __init__(self, func_token: PeekToken, options_tokens: Iterable[PeekToken]):
        self.func_token = func_token
        self.options_tokens = options_tokens

    @property
    def func_name(self):
        return self.func_token.value

    @property
    def options(self):
        # TODO: more feature rich and robust argument parsing
        options = {}
        for t in self.options_tokens:
            k, v = t.value.split('=', 1)
            options[k] = v
        return options

    def execute(self, vm):
        return vm.execute_special(self)

    def format_compact(self):
        # Always use the raw token here to preserve user input (case, quotes etc)
        parts = ['%', self.func_token.value]
        for option_token in self.options_tokens:
            parts.append(option_token.value)
        parts.append('\n')
        return ' '.join(parts)

    def format_pretty(self):
        return self.format_compact()

    def __str__(self):
        return f'%{self.func_name} {self.options}'


class EsApiStmt(Stmt):

    def __init__(self,
                 method_token: PeekToken,
                 path_token: PeekToken,
                 payload_tokens: List[List[PeekToken]]):
        self.method_token = method_token
        self.path_token = path_token
        self.payload_tokens = payload_tokens

    @property
    def method(self):
        return self.method_token.value.upper()

    @property
    def path(self):
        return (self.path_token.value if self.path_token.value.startswith('/')
                else ('/' + self.path_token.value))

    @property
    def payload(self):
        lines = []
        for tokens in self.payload_tokens:
            parts = []
            for t in tokens:
                if t.ttype in (PayloadKey, String.Double, String.Single, TripleS, TripleD):
                    parts.append(normalise_string(t.value))
                else:
                    parts.append(t.value)
            lines.append(' '.join(parts))
        return '\n'.join(lines) + '\n' if lines else None

    def execute(self, vm):
        return vm.execute_es_api_call(self)

    def format_compact(self):
        parts = [self.method_token.value, ' ', self.path_token.value, '\n']
        for tokens in self.payload_tokens:
            parts += [t.value for t in tokens]
            parts.append('\n')
        parts.append('\n')
        return ''.join(parts)

    def format_pretty(self):
        parts = [self.method_token.value, ' ', self.path_token.value, '\n']
        for tokens in self.payload_tokens:
            parts += self._format_pretty_helper(tokens)
        parts.append('\n')
        return ''.join(parts)

    def _format_pretty_helper(self, tokens: List[PeekToken]):
        parts = []
        indent_level = 0
        for i, t in enumerate(tokens):
            assert indent_level >= 0
            # comma or colon always directly follow
            if t.ttype is Comma:
                parts += [t.value, '\n']
            elif t.ttype is Colon:
                parts += [t.value, ' ']
            elif tokens[i - 1].ttype is Colon:  # single space after colon
                parts += [t.value]
            elif t.ttype not in (CurlyRight, BracketRight):
                if indent_level > 0:
                    parts.append('  ' * indent_level)
                parts.append(t.value)

            if t.ttype in (CurlyLeft, BracketLeft):
                # We can be sure there is i+1 token since parser guarantees it
                if tokens[i + 1].ttype not in (CurlyRight, BracketRight):
                    parts.append('\n')
                    indent_level += 1
            elif t.ttype in (CurlyRight, BracketRight):
                if tokens[i - 1].ttype not in (CurlyLeft, BracketLeft):
                    parts.append('\n')
                    indent_level -= 1
                    if indent_level > 0:
                        parts.append('  ' * indent_level)
                parts.append(t.value)
        parts.append('\n')
        return parts

    def __str__(self):
        return f'{self.method} {self.path}' + ('\n' + self.payload if self.payload else '')


class PeekParser:

    def __init__(self):
        self.lexer = PeekLexer()
        self.text = ''
        self.position = 0
        self.tokens = []

    def parse(self, text):
        self.text = text
        self.position = 0
        self.tokens = []

        unprocessed_tokens = []
        for t in self.lexer.get_tokens_unprocessed(self.text):
            token = PeekToken(*t)
            unprocessed_tokens.append(token)
            if token.ttype in Token.Error:
                raise PeekSyntaxError(self.text, token)
        self.tokens = process_tokens(unprocessed_tokens)

        stmts = []
        while self._peek_token().ttype is not EOF:
            token = self._peek_token()
            if token.ttype is BlankLine:
                self._consume_token(BlankLine)
            elif token.ttype is Percent:
                stmts.append(self._parse_special())
            elif token.ttype is Keyword:
                stmts.append(self._parse_es_api_call())
            else:
                raise PeekSyntaxError(
                    self.text, token,
                    title='Invalid token',
                    message='Expect either a "%" or HTTP method')
        return stmts

    def _parse_es_api_call(self):
        method_token = self._consume_token(Keyword)
        if method_token.value.upper() not in HTTP_METHODS:
            raise PeekSyntaxError(
                self.text, method_token,
                title='Invalid HTTP method',
                message=f'Expect HTTP method of value in {HTTP_METHODS!r}, got {method_token.value!r}')
        path_token = self._consume_token(Literal)
        payloads = []
        while self._peek_token().ttype is not EOF:
            if self._peek_token().ttype is BlankLine:
                self._consume_token(BlankLine)
                break
            payloads.append(self._parse_json_object())
        return EsApiStmt(method_token, path_token, payloads)

    def _parse_json_object(self):
        tokens = [self._consume_token(CurlyLeft)]
        has_trailing_comma = False
        while self._peek_token().ttype is not CurlyRight:
            tokens += self._parse_json_kv()
            if self._peek_token().ttype is Comma:
                has_trailing_comma = True
                tokens.append(self._consume_token(Comma))
            else:
                has_trailing_comma = False
                break

        if has_trailing_comma:
            tokens.pop()
        tokens.append(self._consume_token(CurlyRight))

        return tokens

    def _parse_json_kv(self):
        tokens = [
            self._consume_token(PayloadKey),
            self._consume_token(Colon)
        ]
        tokens += self._parse_json_value()
        return tokens

    def _parse_json_array(self):
        tokens = [self._consume_token(BracketLeft)]
        has_trailing_comma = False
        while self._peek_token().ttype is not BracketRight:
            tokens += self._parse_json_value()
            if self._peek_token().ttype is Comma:
                has_trailing_comma = True
                tokens.append(self._consume_token(Comma))
            else:
                has_trailing_comma = False
                break

        if has_trailing_comma:
            tokens.pop()
        tokens.append(self._consume_token(BracketRight))

        return tokens

    def _parse_json_value(self):
        token = self._peek_token()
        if token.ttype is CurlyLeft:
            return self._parse_json_object()
        elif token.ttype is BracketLeft:
            return self._parse_json_array()
        elif token.ttype in Number or token.ttype is Name.Builtin:
            return [self._consume_token(token.ttype)]
        elif token.ttype in (String.Double, String.Single, TripleS, TripleD):
            return [self._consume_token(token.ttype)]
        else:
            raise PeekSyntaxError(self.text, token)

    def _parse_special(self):
        self._consume_token(Percent),
        func_token = self._consume_token(SpecialFunc)
        options_tokens = []
        while self._peek_token().ttype is not EOF:
            if self._peek_token().ttype is BlankLine:
                self._consume_token(BlankLine)
                break
            options_tokens.append(self._consume_token(Literal))
        return SpecialStmt(func_token, options_tokens)

    def _peek_token(self) -> PeekToken:
        if self.position >= len(self.tokens):
            return PeekToken(len(self.text), EOF, '\0')
        return self.tokens[self.position]

    def _consume_token(self, ttype, value=None) -> PeekToken:
        token = self._peek_token()
        self.position += 1
        if token.ttype is not ttype:
            raise PeekSyntaxError(self.text, token,
                                  message=f'Expect token of type {ttype!r}, got {token.ttype!r}')
        if value and (token.value != value or token.value not in value):
            raise PeekSyntaxError(self.text, token,
                                  message=f'Expect token of value {value!r}, got {token.value!r}')
        return token


def normalise_string(value):
    return json.dumps(ast.literal_eval(value))


def process_tokens(tokens: List[PeekToken]):
    """
    Process tokens by filtering out whitespaces and merging tokens that
    should be represented as one, e.g. Strings, BlankLine.
    """
    processed_tokens = []
    current_token = None
    for token in tokens:
        if token.ttype in (Whitespace, Comment.Single):
            if current_token is not None:
                processed_tokens.append(current_token)
                current_token = None
        elif token.ttype in String or token.ttype is BlankLine:
            if current_token is not None and current_token.ttype is token.ttype:
                current_token = PeekToken(
                    current_token.index, current_token.ttype, current_token.value + token.value)
            else:
                # two consecutive strings with different quotes should not be merged
                if current_token is not None:
                    processed_tokens.append(current_token)
                current_token = token
        else:
            if current_token is not None:
                processed_tokens.append(current_token)
                current_token = None
            processed_tokens.append(token)
    if current_token is not None:
        processed_tokens.append(current_token)

    _logger.debug(f'merged tokens: {processed_tokens}')
    return processed_tokens
