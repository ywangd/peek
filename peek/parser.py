import ast
import json
import logging
from enum import Enum
from typing import Iterable, NamedTuple, Callable

from pygments.token import Token, Whitespace, String, Comment, Literal, Number, Name, Error

from peek.ast import NameNode, FuncCallNode, KeyValueNode, StringNode, NumberNode, TextNode, DictNode, \
    ArrayNode, ShellOutNode, EsApiCallInlinePayloadNode, EsApiCallFilePayloadNode, BinOpNode, UnaryOpNode, GroupNode, \
    SymbolNode, LetNode, ForInNode
from peek.common import PeekToken, HTTP_METHODS
from peek.errors import PeekSyntaxError
from peek.lexers import PeekLexer, BlankLine, CurlyLeft, DictKey, Colon, \
    CurlyRight, Comma, BracketLeft, BracketRight, TripleS, TripleD, EOF, FuncName, Assign, HttpMethod, OptionName, \
    ShellOut, At, ParenLeft, ParenRight, UnaryOp, BinOp, Let, For, In

_logger = logging.getLogger(__name__)

HTTP_METHODS = [m.upper() for m in HTTP_METHODS]

_BIN_OP_ORDERS = {
    None: -1,
    '+': 100,
    '-': 100,
    '*': 200,
    '/': 200,
    '%': 200,
    '.': 300,
}


class ParserEventType(Enum):
    ES_METHOD = 'ES_METHOD'
    ES_URL = 'ES_URL'
    BEFORE_ES_URL_EXPR = 'BEFORE_ES_URL_EXPR'
    AFTER_ES_URL_EXPR = 'AFTER_ES_URL_EXPR'
    ES_OPTION_NAME = 'ES_OPTION_NAME'
    BEFORE_ES_OPTION_VALUE = 'BEFORE_ES_OPTION_VALUE'
    AFTER_ES_OPTION_VALUE = 'AFTER_ES_OPTION_VALUE'
    ES_PAYLOAD_FILE_AT = 'ES_PAYLOAD_FILE_AT'
    BEFORE_ES_PAYLOAD_INLINE = 'BEFORE_ES_PAYLOAD_INLINE'
    AFTER_ES_PAYLOAD_INLINE = 'AFTER_ES_PAYLOAD_INLINE'
    FUNC_STMT = 'FUNC_STMT'
    BEFORE_FUNC_ARGS = 'BEFORE_FUNC_ARGS'
    AFTER_FUNC_ARGS = 'AFTER_FUNC_ARGS'
    BEFORE_FUNC_REGULAR_ARG = 'BEFORE_FUNC_REGULAR_ARG'
    AFTER_FUNC_REGULAR_ARG = 'AFTER_FUNC_REGULAR_ARG'
    BEFORE_FUNC_SYMBOL_ARG = 'BEFORE_FUNC_SYMBOL_ARG'
    AFTER_FUNC_SYMBOL_ARG = 'AFTER_FUNC_SYMBOL_ARG'
    FUNC_OPTION_NAME_OR_ARG = 'FUNC_OPTION_NAME_OR_ARG'
    BEFORE_FUNC_OPTION_VALUE = 'BEFORE_FUNC_OPTION_VALUE'
    AFTER_FUNC_OPTION_VALUE = 'AFTER_FUNC_OPTION_VALUE'
    SHELL_OUT = 'SHELL_OUT'
    LET = 'LET'
    FOR = 'FOR'
    BEFORE_FOR_SUITE = 'BEFORE_FOR_SUITE'
    AFTER_FOR_SUITE = 'AFTER_FOR_SUITE'
    DICT_KEY = 'DICT_KEY'
    BEFORE_DICT_KEY_EXPR = 'BEFORE_DICT_KEY_EXPR'
    AFTER_DICT_KEY_EXPR = 'AFTER_DICT_KEY_EXPR'
    BEFORE_DICT_VALUE = 'BEFORE_DICT_VALUE'
    AFTER_DICT_VALUE = 'AFTER_DICT_VALUE'
    AFTER_TOKEN = 'AFTER_TOKEN'


# Event to be published right before the actual parsing
ParserEvent = NamedTuple('ParsingEvent', [('type', ParserEventType), ('token', PeekToken)])


class PeekParser:
    """
    The parser is not thread safe and does not pretend to be.
    """

    def __init__(self, listeners=None):
        self.lexer = PeekLexer()
        self.text = ''
        self.position = 0  # position is token position, not character
        self.tokens = []
        self.listeners: Iterable[Callable] = listeners or []

    def parse(self, text, payload_only=False, fail_fast_on_error_token=True, last_stmt_only=False, log_level=None):
        saved_log_level = _logger.getEffectiveLevel()
        try:
            if log_level is not None:
                _logger.setLevel(log_level)
            self.text = text
            self.position = 0
            self.tokens = []

            stack = ('dict',) if payload_only else ('root',)
            self.tokens = process_tokens(self.lexer.get_tokens_unprocessed(self.text, stack=stack))
            if last_stmt_only:
                idx_last_stmt_token = find_last_stmt_token(self.tokens)
                if idx_last_stmt_token == -1:
                    return []
                else:
                    self.position = idx_last_stmt_token

            if fail_fast_on_error_token:
                for token in self.tokens[self.position:]:
                    if token.ttype in Token.Error:
                        raise PeekSyntaxError(self.text, token, message='Found error token and fail fast is enabled')

            return self._do_parse_payload() if payload_only else self._do_parse()
        finally:
            if log_level is not None:
                _logger.setLevel(saved_log_level)

    def _do_parse(self):
        nodes = []
        while self._peek_token().ttype is not EOF:
            token = self._peek_token()
            if token.ttype is BlankLine:
                self._consume_token(BlankLine)
            else:
                nodes.append(self._parse_stmt())
        return nodes

    def _do_parse_payload(self):
        nodes = []
        while self._peek_token().ttype is not EOF:
            nodes.append(self._parse_dict())
        return nodes

    def _parse_stmt(self):
        token = self._peek_token()
        if token.ttype is FuncName:
            return self._parse_func_call()
        elif token.ttype is HttpMethod:
            return self._parse_es_api_call()
        elif token.ttype is Let:
            return self._parse_let_stmt()
        elif token.ttype is ShellOut:
            return self._parse_shell_out()
        elif token.ttype is For:
            return self._parse_for_stmt()
        else:
            raise PeekSyntaxError(
                self.text, token,
                title='Invalid token',
                message='Expect beginning of a statement')

    def _parse_es_api_call(self):
        self._publish_event(ParserEventType.ES_METHOD)
        method_token = self._consume_token(HttpMethod)
        method_node = NameNode(method_token)
        if method_token.value.upper() not in HTTP_METHODS:
            raise PeekSyntaxError(
                self.text, method_token,
                title='Invalid HTTP method',
                message=f'Expect HTTP method of value in {HTTP_METHODS!r}, got {method_token.value!r}')

        if self._peek_token().ttype is Literal:
            self._publish_event(ParserEventType.ES_URL)
            path_node = TextNode(self._consume_token(Literal))
        elif self._peek_token().ttype is ParenLeft:
            self._publish_event(ParserEventType.BEFORE_ES_URL_EXPR)
            path_node = self._parse_expr()
            self._publish_event(ParserEventType.AFTER_ES_URL_EXPR)
        else:
            raise PeekSyntaxError(
                self.text, self._peek_token(),
                message='HTTP path must be either text literal or an expression enclosed by parenthesis')

        option_nodes = []
        while self._peek_token().ttype is OptionName:
            self._publish_event(ParserEventType.ES_OPTION_NAME)
            n = NameNode(self._consume_token(OptionName))
            self._consume_token(Assign)
            self._publish_event(ParserEventType.BEFORE_ES_OPTION_VALUE)
            option_nodes.append(KeyValueNode(n, self._parse_expr()))
            self._publish_event(ParserEventType.AFTER_ES_OPTION_VALUE)

        if self._peek_token().ttype is At:
            self._publish_event(ParserEventType.ES_PAYLOAD_FILE_AT)
            self._consume_token(At)
            return EsApiCallFilePayloadNode(
                method_node, path_node, DictNode(option_nodes), TextNode(self._consume_token(Literal)))
        else:
            dict_nodes = []
            while self._peek_token().ttype is not EOF:
                if self._peek_token().ttype is CurlyLeft:
                    self._publish_event(ParserEventType.BEFORE_ES_PAYLOAD_INLINE)
                    dict_nodes.append(self._parse_dict())
                    self._publish_event(ParserEventType.AFTER_ES_PAYLOAD_INLINE)
                else:
                    break
            return EsApiCallInlinePayloadNode(method_node, path_node, DictNode(option_nodes), dict_nodes)

    def _parse_let_stmt(self):
        self._publish_event(ParserEventType.LET)
        self._consume_token(Let)
        kv_nodes = []
        while self._peek_token().ttype is not EOF:
            if self._peek_token().ttype is BlankLine:
                self._consume_token(BlankLine)
                break
            key_node = self._parse_expr()
            self._consume_token(Assign)
            value_node = self._parse_expr()
            kv_nodes.append(KeyValueNode(key_node, value_node))
        return LetNode(DictNode(kv_nodes))

    def _parse_for_stmt(self):
        self._publish_event(ParserEventType.FOR)
        self._consume_token(For)
        item = NameNode(self._consume_token(Name))
        self._consume_token(In)
        items = self._parse_expr()
        self._publish_event(ParserEventType.BEFORE_FOR_SUITE)
        self._consume_token(CurlyLeft)
        suite = []
        while self._peek_token().ttype is not CurlyRight:
            token = self._peek_token()
            if token.ttype is BlankLine:
                self._consume_token(BlankLine)
            else:
                suite.append(self._parse_stmt())
        self._consume_token(CurlyRight)
        self._publish_event(ParserEventType.AFTER_FOR_SUITE)
        return ForInNode(item, items, suite)

    def _parse_dict(self):
        kv_nodes = []
        self._consume_token(CurlyLeft)
        while self._peek_token().ttype is not CurlyRight:
            kv_nodes.append(self._parse_dict_kv())
            if self._peek_token().ttype is Comma:
                self._consume_token(Comma)
            else:
                break
        self._consume_token(CurlyRight)
        return DictNode(kv_nodes)

    def _parse_dict_kv(self):
        if self._peek_token().ttype is DictKey:
            self._publish_event(ParserEventType.DICT_KEY)
            key_node = StringNode(self._consume_token(DictKey))
        else:
            self._publish_event(ParserEventType.BEFORE_DICT_KEY_EXPR)
            key_node = self._parse_expr()
            self._publish_event(ParserEventType.AFTER_DICT_KEY_EXPR)
        self._consume_token(Colon)
        self._publish_event(ParserEventType.BEFORE_DICT_VALUE)
        value_node = self._parse_expr()
        self._publish_event(ParserEventType.AFTER_DICT_VALUE)
        return KeyValueNode(key_node, value_node)

    def _parse_array(self):
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

    def _parse_value(self):
        token = self._peek_token()
        if token.ttype is CurlyLeft:
            return self._parse_dict()
        elif token.ttype is BracketLeft:
            return self._parse_array()
        elif token.ttype in Number:
            return NumberNode(self._consume_token(token.ttype))
        elif token.ttype is Name.Builtin:
            return TextNode(self._consume_token(token.ttype))
        elif token.ttype in (String.Double, String.Single, TripleS, TripleD):
            return StringNode(self._consume_token(token.ttype))
        else:
            raise PeekSyntaxError(self.text, token, message=f'Unexpected token when parsing for value: {token!r}')

    def _parse_func_call(self):
        self._publish_event(ParserEventType.FUNC_STMT)
        name_node = NameNode(self._consume_token(FuncName))
        symbol_nodes, arg_nodes, kwarg_nodes = self._parse_func_call_args()
        return FuncCallNode(name_node, ArrayNode(symbol_nodes), ArrayNode(arg_nodes), DictNode(kwarg_nodes))

    def _parse_func_call_args(self, is_stmt=True):
        self._publish_event(ParserEventType.BEFORE_FUNC_ARGS)
        symbol_nodes = []
        arg_nodes = []
        kwarg_nodes = []
        while self._peek_token().ttype is not EOF:
            if self._peek_token().ttype is BlankLine:
                self._consume_token(BlankLine)
                if is_stmt:
                    break
            elif self._peek_token().ttype is ParenRight:
                if is_stmt:
                    raise PeekSyntaxError(
                        self.text, self._peek_token(),
                        message='Found function expression while parsing for function stmt')
                else:
                    break
            elif self._peek_token().ttype is Name:
                self._publish_event(ParserEventType.FUNC_OPTION_NAME_OR_ARG)
                n = NameNode(self._consume_token(Name))
                if self._peek_token().ttype is Assign:
                    self._consume_token(Assign)
                    self._publish_event(ParserEventType.BEFORE_FUNC_OPTION_VALUE)
                    kwarg_nodes.append(KeyValueNode(n, self._parse_expr()))
                    self._publish_event(ParserEventType.AFTER_FUNC_OPTION_VALUE)
                else:
                    arg_nodes.append(self._parse_expr_after_left_operand(n))
            elif self._peek_token().ttype is At:
                self._publish_event(ParserEventType.BEFORE_FUNC_SYMBOL_ARG)
                self._consume_token(At)
                symbol_nodes.append(SymbolNode(self._consume_token(Literal)))
                self._publish_event(ParserEventType.AFTER_FUNC_SYMBOL_ARG)
            else:
                self._publish_event(ParserEventType.BEFORE_FUNC_REGULAR_ARG)
                arg_nodes.append(self._parse_expr())
                self._publish_event(ParserEventType.AFTER_FUNC_REGULAR_ARG)
        self._publish_event(ParserEventType.AFTER_FUNC_ARGS)
        return symbol_nodes, arg_nodes, kwarg_nodes

    def _parse_shell_out(self):
        self._publish_event(ParserEventType.SHELL_OUT)
        self._consume_token(ShellOut)
        return ShellOutNode(TextNode(self._consume_token(Literal)))

    def _parse_expr(self, last_bin_op=None):
        if self._peek_token().ttype is UnaryOp:
            unary_op_token = self._consume_token(UnaryOp)
        else:
            unary_op_token = None

        if self._peek_token().ttype is ParenLeft:
            pl = self._consume_token(ParenLeft)
            n = self._parse_expr()
            pr = self._consume_token(ParenRight)
            n = GroupNode(n, pl, pr)
        elif self._peek_token().ttype is Name:
            n = NameNode(self._consume_token(Name))
        elif self._peek_token().ttype is At:
            self._consume_token(At)
            n = SymbolNode(self._consume_token(Literal))
        else:
            n = self._parse_value()

        return self._parse_expr_after_left_operand(n, unary_op_token=unary_op_token, last_bin_op=last_bin_op)

    def _parse_expr_after_left_operand(self, n, unary_op_token=None, last_bin_op=None):
        while True:
            if self._peek_token().ttype is BinOp:
                op_token = self._peek_token()
                if _BIN_OP_ORDERS[last_bin_op] >= _BIN_OP_ORDERS[op_token.value]:
                    return n if unary_op_token is None else UnaryOpNode(unary_op_token, n)
                else:
                    self._consume_token(op_token.ttype)
                    right_node = self._parse_expr(last_bin_op=op_token.value)
                    n = n if unary_op_token is None else UnaryOpNode(unary_op_token, n)
                    n = BinOpNode(op_token, n, right_node)
            elif self._peek_token().ttype is ParenLeft:  # func call
                if last_bin_op == '.':
                    return n if unary_op_token is None else UnaryOpNode(unary_op_token, n)
                else:
                    self._consume_token(ParenLeft)
                    symbol_nodes, arg_nodes, kwarg_nodes = self._parse_func_call_args(is_stmt=False)
                    self._consume_token(ParenRight)
                    n = FuncCallNode(
                        n,
                        ArrayNode(symbol_nodes),
                        ArrayNode(arg_nodes),
                        DictNode(kwarg_nodes),
                        is_stmt=False
                    )
                    n = n if unary_op_token is None else UnaryOpNode(unary_op_token, n)
            else:
                return n if unary_op_token is None else UnaryOpNode(unary_op_token, n)
            unary_op_token = None

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
        self._publish_event(ParserEventType.AFTER_TOKEN, token)
        return token

    def _publish_event(self, event_type: ParserEventType, token=None):
        token = token or self._peek_token()
        for listener in self.listeners:
            listener(ParserEvent(event_type, token))


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

    return processed_tokens


def find_last_stmt_token(tokens) -> int:
    """
    Find the last token that can start a statement
    """
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i].ttype in (HttpMethod, FuncName, ShellOut, Let, For):
            return i
    return -1
