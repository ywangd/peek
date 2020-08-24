import ast
import json
import logging
from typing import Iterable

from pygments.token import Token, Whitespace, String, Comment, Literal, Number, Name, Error

from peek.ast import NameNode, FuncCallNode, KeyValueNode, StringNode, NumberNode, TextNode, DictNode, \
    ArrayNode, ShellOutNode, EsApiCallInlinePayloadNode, EsApiCallFilePayloadNode
from peek.common import PeekToken
from peek.errors import PeekSyntaxError
from peek.lexers import PeekLexer, BlankLine, CurlyLeft, DictKey, Colon, \
    CurlyRight, Comma, BracketLeft, BracketRight, TripleS, TripleD, EOF, FuncName, Assign, HttpMethod, OptionName, \
    ShellOut, At

_logger = logging.getLogger(__name__)

HTTP_METHODS = ['GET', 'PUT', 'POST', 'DELETE']


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

        self.tokens = process_tokens(self.lexer.get_tokens_unprocessed(self.text))
        for token in self.tokens:
            if token.ttype in Token.Error:
                raise PeekSyntaxError(self.text, token)

        nodes = []
        while self._peek_token().ttype is not EOF:
            token = self._peek_token()
            if token.ttype is BlankLine:
                self._consume_token(BlankLine)
            elif token.ttype is FuncName:
                nodes.append(self._parse_func_call())
            elif token.ttype is HttpMethod:
                nodes.append(self._parse_es_api_call())
            elif token.ttype is ShellOut:
                nodes.append(self._parse_shell_command())
            else:
                raise PeekSyntaxError(
                    self.text, token,
                    title='Invalid token',
                    message='Expect beginning of a statement')
        return nodes

    def _parse_es_api_call(self):
        method_token = self._consume_token(HttpMethod)
        method_node = NameNode(method_token)
        if method_token.value.upper() not in HTTP_METHODS:
            raise PeekSyntaxError(
                self.text, method_token,
                title='Invalid HTTP method',
                message=f'Expect HTTP method of value in {HTTP_METHODS!r}, got {method_token.value!r}')
        path_node = NameNode(self._consume_token(Literal))
        option_nodes = []
        while self._peek_token().ttype is OptionName:
            n = NameNode(self._consume_token(OptionName))
            self._consume_token(Assign)
            option_nodes.append(KeyValueNode(n, self._parse_expr()))

        if self._peek_token().ttype is At:
            self._consume_token(At)
            return EsApiCallFilePayloadNode(
                method_node, path_node, DictNode(option_nodes), TextNode(self._consume_token(Literal)))
        else:
            dict_nodes = []
            while self._peek_token().ttype is not EOF:
                if self._peek_token().ttype is CurlyLeft:
                    dict_nodes.append(self._parse_json_object())
                else:
                    break
            return EsApiCallInlinePayloadNode(method_node, path_node, DictNode(option_nodes), dict_nodes)

    def _parse_json_object(self):
        kv_nodes = []
        self._consume_token(CurlyLeft)
        while self._peek_token().ttype is not CurlyRight:
            kv_nodes.append(self._parse_json_kv())
            if self._peek_token().ttype is Comma:
                self._consume_token(Comma)
            else:
                break
        self._consume_token(CurlyRight)
        return DictNode(kv_nodes)

    def _parse_json_kv(self):
        key_node = StringNode(self._consume_token(DictKey))
        self._consume_token(Colon)
        value_node = self._parse_expr()
        return KeyValueNode(key_node, value_node)

    def _parse_json_array(self):
        value_nodes = []
        self._consume_token(BracketLeft)
        while self._peek_token().ttype is not BracketRight:
            value_nodes.append(self._parse_expr())
            if self._peek_token().ttype is Comma:
                self._consume_token(Comma)
            else:
                break
        self._consume_token(BracketRight)
        return ArrayNode(value_nodes)

    def _parse_json_value(self):
        token = self._peek_token()
        if token.ttype is CurlyLeft:
            return self._parse_json_object()
        elif token.ttype is BracketLeft:
            return self._parse_json_array()
        elif token.ttype in Number:
            return NumberNode(self._consume_token(token.ttype))
        elif token.ttype is Name.Builtin:
            return TextNode(self._consume_token(token.ttype))
        elif token.ttype in (String.Double, String.Single, TripleS, TripleD):
            return StringNode(self._consume_token(token.ttype))
        else:
            raise PeekSyntaxError(self.text, token)

    def _parse_func_call(self):
        name_node = NameNode(self._consume_token(FuncName))
        cmd_nodes = []
        arg_nodes = []
        kwarg_nodes = []
        while self._peek_token().ttype is not EOF:
            if self._peek_token().ttype is BlankLine:
                self._consume_token(BlankLine)
                break
            if self._peek_token().ttype is Name:
                n = NameNode(self._consume_token(Name))
                if self._peek_token().ttype is Assign:
                    self._consume_token(Assign)
                    kwarg_nodes.append(KeyValueNode(n, self._parse_expr()))
                else:
                    arg_nodes.append(n)
            elif self._peek_token().ttype is At:
                self._consume_token(At)
                cmd_nodes.append(TextNode(self._consume_token(Literal)))
            else:
                arg_nodes.append(self._parse_expr())

        return FuncCallNode(name_node, ArrayNode(cmd_nodes), ArrayNode(arg_nodes), DictNode(kwarg_nodes))

    def _parse_shell_command(self):
        self._consume_token(ShellOut)
        return ShellOutNode(TextNode(self._consume_token(Literal)))

    def _parse_expr(self):
        if self._peek_token().ttype is Name:
            return NameNode(self._consume_token(Name))
        else:
            return self._parse_json_value()

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


def process_tokens(tokens: Iterable[PeekToken]):
    """
    Process tokens by filtering out whitespaces and merging tokens that
    should be represented as one, e.g. Strings, BlankLine, Error.
    """
    processed_tokens = []
    current_token = None
    for token in tokens:
        if token.ttype in (Whitespace, Comment.Single):
            if current_token is not None:
                processed_tokens.append(current_token)
                current_token = None
        elif token.ttype in String or token.ttype is BlankLine or token.ttype is Error:
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

    _logger.debug(f'processed tokens: {processed_tokens}')
    return processed_tokens
