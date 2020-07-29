import ast
import json
import logging
from abc import ABCMeta, abstractmethod
from typing import Dict, Optional, List, NamedTuple

from pygments.token import Token, Whitespace, String, Comment, Literal, Keyword, Number, Name, _TokenType

from peek.errors import PeekSyntaxError
from peek.lexers import PeekLexer, BlankLine, Percent, SpecialFunc, HTTP_METHODS, CurlyLeft, PayloadKey, Colon, \
    CurlyRight, Comma, BracketLeft, BracketRight, TripleS, TripleD

_logger = logging.getLogger(__name__)

PeekToken = NamedTuple('PeekToken', [('index', int), ('ttype', _TokenType), ('value', str)])


class Stmt(metaclass=ABCMeta):

    @abstractmethod
    def execute(self, vm):
        pass

    def __repr__(self):
        return str(self)


class SpecialStmt(Stmt):

    def __init__(self, func_name: str, options: Dict):
        self.func_name = func_name
        self.options = options

    def execute(self, vm):
        return vm.execute_special(self)

    def __str__(self):
        return f'%{self.func_name} {self.options}'


class EsApiStmt(Stmt):

    def __init__(self, method: str, path: str, payload: Optional[str]):
        self.method = method
        self.path = path if path.startswith('/') else ('/' + path)
        self.payload = payload

    def execute(self, vm):
        return vm.execute_es_api_call(self)

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
        while True:
            try:
                token = self._peek_token()
            except EOFError:
                break
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
        lines = []
        while True:
            try:
                token = self._peek_token()
                if token.ttype == BlankLine:
                    break
            except EOFError:
                break
            lines.append(' '.join(self._parse_json_object()))
        return EsApiStmt(method_token.value.upper(), path_token.value,
                         '\n'.join(lines) + '\n' if lines else None)

    def _parse_json_object(self):
        parts = [self._consume_token(CurlyLeft).value]
        has_trailing_comma = False
        while self._peek_token().ttype is not CurlyRight:
            has_trailing_comma = False
            parts += self._parse_json_kv()
            if self._peek_token().ttype is Comma:
                has_trailing_comma = True
                parts.append(self._consume_token(Comma).value)

        if has_trailing_comma:
            parts.pop()
        parts.append(self._consume_token(CurlyRight).value)

        return parts

    def _parse_json_kv(self):
        parts = [
            normalise_string(self._consume_token(PayloadKey).value),
            self._consume_token(Colon).value
        ]
        parts += self._parse_json_value()
        return parts

    def _parse_json_array(self):
        parts = [self._consume_token(BracketLeft).value]
        has_trailing_comma = False
        while self._peek_token().ttype is not BracketRight:
            has_trailing_comma = False
            parts += self._parse_json_value()
            if self._peek_token().ttype is Comma:
                has_trailing_comma = True
                parts.append(self._consume_token(Comma).value)

        if has_trailing_comma:
            parts.pop()
        parts.append(self._consume_token(BracketRight).value)

        return parts

    def _parse_json_value(self):
        token = self._peek_token()
        if token.ttype is CurlyLeft:
            return self._parse_json_object()
        elif token.ttype is BracketLeft:
            return self._parse_json_array()
        elif token.ttype in Number or token.ttype is Name.Builtin:
            return [self._consume_token(token.ttype).value]
        elif token.ttype in (String.Double, String.Single, TripleS, TripleD):
            return [normalise_string(self._consume_token(token.ttype).value)]
        else:
            raise PeekSyntaxError(self.text, token)

    def _parse_special(self):
        self._consume_token(Percent)
        func_token = self._consume_token(SpecialFunc)
        arg_tokens = []
        while True:
            if self._peek_token().ttype is BlankLine:
                break
            arg_tokens.append(self._consume_token(Literal))

        # TODO: more feature rich and robust argument parsing
        options = {}
        for t in arg_tokens:
            k, v = t.value.split('=', 1)
            options[k] = v
        return SpecialStmt(func_token.value, options)

    def _peek_token(self) -> PeekToken:
        if self.position >= len(self.tokens):
            raise EOFError()
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
