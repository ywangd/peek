import re
from typing import Iterable

from pygments.lexer import RegexLexer, words, include, bygroups, default
from pygments.style import Style
from pygments.token import Keyword, Literal, String, Number, Punctuation, Name, Comment, Whitespace, Generic, Error, \
    Operator, Text

from peek.common import PeekToken
from peek.errors import PeekSyntaxError

Percent = Punctuation.Percent
CurlyLeft = Punctuation.Curly.Left
CurlyRight = Punctuation.Curly.Right
BracketLeft = Punctuation.Bracket.Left
BracketRight = Punctuation.Bracket.Right
ParenLeft = Punctuation.Paren.Left
ParenRight = Punctuation.Paren.Right
Comma = Punctuation.Comma
Colon = Punctuation.Colon
At = Punctuation.At
Heading = Generic.Heading
TripleD = String.TripleD
TripleS = String.TripleS
Assign = Operator.Assign
BinOp = Operator.BinOp
UnaryOp = Operator.UnaryOp
BlankLine = Whitespace.BlankLine
FuncName = Name.Variable
HttpMethod = Keyword.HttpMethod
Let = Keyword.Let
For = Keyword.For
In = Keyword.In
ShellOut = Punctuation.Bang
DictKey = String.Symbol
OptionName = Name.Symbol

TipsMinor = Generic.TipsMinor
EOF = Whitespace.EOF

VARIABLE_PATTERN = r'\b[_a-zA-Z]+[_a-zA-Z0-9]*\b'


class PeekStyle(Style):
    default_style = ''
    # null: #445
    styles = {
        Keyword: '#03F147',
        Literal: '#FFFCF9',
        DictKey: '#bff',  # '#28b',
        String: '#395',
        Name.Builtin: '#77f',
        FuncName: '#77f',
        Number: '#07a',
        Heading: '#F6D845',
        TipsMinor: '#4C4447',
        Error: 'bg:#a40000',
    }


def dqs(ttype):
    return [
        (r'"', ttype, '#pop'),  # end of string
        (r'\\.', ttype),  # process escapes separately
        # Inner string, not allow multiline, not processing end of string,
        # also don't consume a single backslash on its own since it is processed above
        # in combination with the char it applies to.
        (r'[^\\\n"]+', ttype),
    ]


def sqs(ttype):
    return [
        (r"'", ttype, '#pop'),
        (r"\\.", ttype),
        (r'[^\\\n\']+', ttype),
    ]


W = r'[ \t\r\f\v]'


# Whitespace should be consumed in parent state, so that child state can simply pop on default no matching
# If there is a signature pattern to signal a #pop, use it and it's ok to consume whitespace. Otherwise,
# default to pop and do not allow consuming whitespace standalone.

class PeekLexer(RegexLexer):
    name = 'ES'
    aliases = ['es']
    filenames = ['*.es']

    tokens = {
        'root': [
            (r'(!)(.*)', bygroups(ShellOut, Literal)),
            (r'//.*', Comment.Single),
            (r'(?i)(GET|POST|PUT|DELETE)\b(' + W + '*)', bygroups(HttpMethod, Whitespace), 'api_path'),
            # TODO: more keywords
            (r'(let)\b(' + W + '*)', bygroups(Let, Whitespace), 'let_args'),
            (r'(for)\b(' + W + '*)', bygroups(For, Whitespace), 'for_name'),
            (VARIABLE_PATTERN, FuncName, 'func_stmt_args'),
            (r'\s+', Whitespace),
        ],
        'stmts': [
            include('root'),
            default('#pop')
        ],
        'let_args': [
            (r'\n', BlankLine, '#pop'),
            (r'//.*', Comment.Single),
            (W + r'*(?=\S)', Whitespace, ('assign_rhs', 'value')),
        ],
        'for_name': [
            (VARIABLE_PATTERN, Name, ('#pop', 'for_in')),
        ],
        'for_in': [
            (W + r'+', Whitespace),
            (r'(in)\b(' + W + r'*)',
             bygroups(In, Whitespace), ('#pop', 'for_body_start', 'value')),
        ],
        'for_body_start': [
            (r'(' + W + r'*)(\{)', bygroups(Whitespace, CurlyLeft), ('#pop', 'for_body_stop', 'stmts')),
        ],
        'for_body_stop': [
            (r'(\s*)(\})', bygroups(Whitespace, CurlyRight), '#pop'),
        ],
        'api_path': [
            (r'(\s*)(?=\()', Whitespace, ('#pop', 'api_options', 'group')),
            (r'\S+', Literal, ('#pop', 'api_options')),
        ],
        'api_options': [
            (r'\n', Whitespace, ('#pop', 'payload')),
            (r'//.*', Comment.Single),
            (VARIABLE_PATTERN, OptionName, 'assign_rhs'),
            (W + r'+', Whitespace),
            # default(('#pop', 'payload')),  # this is to make the newline optional
        ],
        'assign_rhs': [
            (r'(' + W + r'*)(=)(' + W + r'*)', bygroups(Whitespace, Assign, Whitespace), ('#pop', 'value')),
        ],
        'payload': [
            (r'(' + W + '*)' + r'(//.*)(\n)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'(' + W + r'*)(?={)', Whitespace, ('#pop', 'payload_cont', 'dict')),
            (r'(' + W + r'*)(@)', bygroups(Whitespace, At), ('#pop', 'payload_file')),
            default('#pop'),  # payload has default pop because it is optional and next statement may begin here
        ],
        'payload_file': [
            (r'\S+', Literal, '#pop'),
        ],
        'payload_cont': [
            (r'(\n' + W + r'*)(//.*)', bygroups(Whitespace, Comment.Single)),
            (r'(\n' + W + r'*)(?={)', Whitespace, 'dict'),
            default('#pop'),  # similar to payload, payload_cont can stop at anytime and next statement may begin
        ],
        'func_stmt_args': [
            (r'\n', BlankLine, '#pop'),
            (r'//.*', Comment.Single),
            (VARIABLE_PATTERN + r'(?=' + W + '*=)', Name, 'func_option'),  # kv pair
            (W + r'+', Whitespace),
            (r',', Whitespace),
            # Instead of include, we should default to get into value because value pop itself out of the stack
            # one it is consumed. If included it, it will pop out the func_stmt_args stage, which is incorrect.
            # func_stmt_args needs has explicit pop by newline.
            default('value'),
        ],
        'func_option': [
            (r'(' + W + r'*)(=)(' + W + r'*)', bygroups(Whitespace, Assign, Whitespace), ('#pop', 'value')),
            default('#pop'),  # func option has default pop because func has positional arg
        ],
        'dict': [
            (r'({)(\s*)', bygroups(CurlyLeft, Whitespace), ('colon', 'dict_key')),
            (r'//.*', Comment.Single),
            (r'\s+', Whitespace),
            (r'}', CurlyRight, '#pop'),
            (r'(,)(\s*)', bygroups(Comma, Whitespace), ('colon', 'dict_key')),
        ],
        # dict_key should not have default pop because of similar reason to value
        'dict_key': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'(\s*)(?=})', Whitespace, '#pop:2'),  # special handle for empty dict and extra comma
            # dict_key does not support triple quotes by itself, but can be used if it is part of an expression
            (r'"(?!"")', DictKey, ('#pop', 'operators', 'dqs_key')),
            (r"'(?!'')", DictKey, ('#pop', 'operators', 'sqs_key')),
            include('value'),
        ],
        'colon': [
            (r'(\s*)(:)(\s*)', bygroups(Whitespace, Colon, Whitespace), ('#pop', 'dict_value')),
        ],
        'dict_value': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            include('value'),
        ],
        'array': [
            (r'(\[)(\s*)', bygroups(BracketLeft, Whitespace), 'array_value'),
            (r'//.*', Comment.Single),
            (r'\s+', Whitespace),
            (r']', BracketRight, '#pop'),
            (r'(,)(\s*)', bygroups(Comma, Whitespace), 'array_value'),
        ],
        'array_value': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'(\s*)(?=\])', Whitespace, '#pop'),  # special handle for empty array and extra comma
            include('value'),
        ],
        'group': [
            (r'(\()(\s*)', bygroups(ParenLeft, Whitespace), 'value'),
            (r'//.*', Comment.Single),
            (r'\s+', Whitespace),
            (r'\)', ParenRight, '#pop'),
        ],
        'group_value': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'(\s*)(?=\))', Whitespace, '#pop'),  # special handle for empty array and extra comma
            include('value'),
        ],
        # Single value should NOT default pop because when the lexer gets here, it should
        # expect exact one value to consume, anything else should be handled by the upstream.
        '_value_common': [
            (r'(' + W + r'*)([-+]?)(?=\()', bygroups(Whitespace, UnaryOp), ('#pop', 'operators', 'group')),
            (r'(' + W + r'*)(?={)', Whitespace, ('#pop', 'operators', 'dict')),
            (r'(' + W + r'*)(?=\[)', Whitespace, ('#pop', 'operators', 'array')),
            (r'"""', TripleD, ('#pop', 'operators', 'tdqs')),
            (r"'''", TripleS, ('#pop', 'operators', 'tsqs')),
            (r'"', String.Double, ('#pop', 'operators', 'dqs')),
            (r"'", String.Single, ('#pop', 'operators', 'sqs')),
            (words(('true', 'false', 'null'), suffix=r'\b'), Name.Builtin, ('#pop', 'operators')),
            # (r'([-+]?)(' + VARIABLE_PATTERN + r')(' + W + r'*)(?=\()',
            #  bygroups(UnaryOp, Name, Whitespace), ('#pop', 'func_expr')),
            (r'([-+]?)(' + VARIABLE_PATTERN + r')', bygroups(UnaryOp, Name), ('#pop', 'operators')),
            (r'@', At, ('#pop', 'operators', 'symbol')),
        ],
        'symbol': [
            (VARIABLE_PATTERN, Literal, '#pop'),
        ],
        'value': [
            include('_value_common'),
            include('numbers'),
        ],
        'dotable_value': [
            include('_value_common'),
            include('integers'),
        ],
        'func_expr': [
            (r'//.*', Comment.Single),
            (W + r'+', Whitespace),
            (r'(\()(\s*)', bygroups(ParenLeft, Whitespace), 'func_expr_args'),
            (r'\)', ParenRight, '#pop'),

        ],
        'func_expr_args': [
            (r'//.*', Comment.Single),
            (r'(\s*)(?=\))', Whitespace, '#pop'),
            (VARIABLE_PATTERN + r'(?=' + W + '*=)', Name, 'func_option'),  # kv pair
            (r'\s+', Whitespace),
            (r',', Whitespace),
            default('value'),
        ],
        'operators': [  # operator cannot be on the new line
            (W + r'+', Whitespace),
            (r'(' + W + r'*)(?=//)', Whitespace, '#pop'),
            (r'([-+*/%])(\s*)', bygroups(BinOp, Whitespace), 'trailing_value'),
            (r'(\.)(\s*)', bygroups(BinOp, Whitespace), 'trailing_dotable_value'),
            (r'(' + W + r'*)(?=\()', Whitespace, 'func_expr'),
            default('#pop')  # pop out when no operators are seen
        ],

        'trailing_value': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'\s+', Whitespace),
            include('value'),
        ],
        'trailing_dotable_value': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'\s+', Whitespace),
            include('dotable_value'),
        ],
        'dqs_key': dqs(DictKey),
        'sqs_key': sqs(DictKey),
        'dqs': dqs(String.Double),
        'sqs': sqs(String.Single),
        'tdqs': [
            (r'"""', TripleD, '#pop'),
            (r'\\\\|\\"|\\|"', TripleD),  # allow escapes
            (r'[^\\"]+', TripleD),  # not cater for multiple line
        ],
        'tsqs': [
            (r"'''", TripleS, '#pop'),
            (r"\\\\|\\'|\\|'", TripleS),  # allow escapes
            (r"[^\\']+", TripleS),  # not cater for multiple line
        ],
        'numbers': [
            (r'[-+]?(\d+\.\d*|\d*\.\d+)([eE][+-]?[0-9]+)?j?', Number.Float, ('#pop', 'operators')),
            (r'[-+]?\d+[eE][+-]?[0-9]+j?', Number.Float, ('#pop', 'operators')),
            (r'[-+]?0[0-7]+j?', Number.Oct, ('#pop', 'operators')),
            (r'[-+]?0[bB][01]+', Number.Bin, ('#pop', 'operators')),
            (r'[-+]?0[xX][a-fA-F0-9]+', Number.Hex, ('#pop', 'operators')),
            include('integers'),
        ],
        'integers': [
            (r'[-+]?\d+L', Number.Integer.Long, ('#pop', 'operators')),
            (r'[-+]?\d+j?', Number.Integer, ('#pop', 'operators')),
        ],
    }
    flags = re.MULTILINE

    def __init__(self, stack=None, **options):
        super().__init__(**options)
        self.stack = stack or ('root',)

    def get_tokens_unprocessed(self, text, stack=None) -> Iterable[PeekToken]:
        """
        Convert DictKey to common string if it is part of an expression
        """
        stack = stack or self.stack
        stream = super().get_tokens_unprocessed(text, stack)
        buffer = []
        while True:
            try:
                pt = PeekToken(*next(stream))
                if pt.ttype is DictKey:
                    assert 0 == len(buffer)
                    buffer.append(pt)
                    while True:
                        pt_next = PeekToken(*next(stream))
                        if pt_next.ttype in (DictKey, Whitespace, Comment.Single):
                            buffer.append(pt_next)
                        elif pt_next.ttype is Colon:
                            buffer.append(pt_next)
                            for t in buffer:
                                yield t
                            buffer = []
                            break
                        else:
                            buffer.append(pt_next)
                            first_token = buffer[0]
                            if first_token.value == "'":
                                actual_type = String.Single
                            elif first_token.value == '"':
                                actual_type = String.Double
                            elif first_token.value == "'''":
                                actual_type = String.TripleS
                            elif first_token.value == '"""':
                                actual_type = String.TripleD
                            else:
                                raise PeekSyntaxError(text, first_token, message='DictKey expected')
                            for t in buffer:
                                if t.ttype is DictKey:
                                    t = PeekToken(t.index, actual_type, t.value)
                                yield t
                            buffer = []
                            break
                else:
                    yield pt

            except StopIteration:
                if buffer:
                    for t in buffer:
                        yield t
                break


Slash = Punctuation.Slash
PathPart = Text.PathPart
QuestionMark = Punctuation.QuestionMark
Ampersand = Punctuation.Ampersand
Pound = Punctuation.Pound
ParamName = Name.ParamName
ParamValue = Text.ParamValue


class UrlPathLexer(RegexLexer):
    name = 'URLPATH'
    aliases = ['url_path']

    tokens = {
        'root': [
            (r'/', Slash),
            (r'[^/?\s]+', PathPart),
            (r'\?', QuestionMark, 'query')
        ],
        'query': [
            (r'&', Ampersand),
            (r'([^=&\s]+)(=)?([^&#\s]+)?', bygroups(ParamName, Assign, ParamValue)),
            (r'#', Pound, ('#pop', 'fragment')),
        ],
        'fragment': [
            (r'\S+', Text),
        ],
    }

    def get_tokens_unprocessed(self, text, stack=('root',)) -> PeekToken:
        for t in super().get_tokens_unprocessed(text, stack):
            yield PeekToken(*t)
