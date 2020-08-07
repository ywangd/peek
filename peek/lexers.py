import re

from pygments.lexer import RegexLexer, words, include, bygroups, default
from pygments.style import Style
from pygments.token import Keyword, Literal, String, Number, Punctuation, Name, Comment, Whitespace, Generic, Error, \
    Operator

from peek.common import PeekToken

Percent = Punctuation.Percent
CurlyLeft = Punctuation.Curly.Left
CurlyRight = Punctuation.Curly.Right
BracketLeft = Punctuation.Bracket.Left
BracketRight = Punctuation.Bracket.Right
Comma = Punctuation.Comma
Colon = Punctuation.Colon
Heading = Generic.Heading
TripleD = String.TripleD
TripleS = String.TripleS
Assign = Operator.Assign
BlankLine = Whitespace.BlankLine
Variable = Name.Variable
PayloadKey = String.Symbol
TipsMinor = Generic.TipsMinor
EOF = Whitespace.EOF

VARIABLE_PATTERN = r'\b[_a-zA-Z]+[_a-zA-Z0-9]*\b'


class PeekStyle(Style):
    default_style = ''
    # null: #445
    styles = {
        Keyword: '#03F147',
        Literal: '#FFFCF9',
        PayloadKey: '#bff',  # '#28b',
        String: '#395',
        Name.Builtin: '#77f',
        Variable: '#77f',
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


DoubleNLPop = (r'(\s*)(\n\s*\n)', bygroups(Whitespace, BlankLine), '#pop')
W = r'[ \t\r\f\v]'


# Whitespace should be consumed in parent state, so that child state can simply pop on default no matching
# If there is a signature pattern to signal a #pop, use it and it's ok to consume whitespace. Otherwise,
# default to pop and do not allow consuming whitespace standalone.

class PeekLexer(RegexLexer):
    name = 'ES'
    aliases = ['es']
    filenames = ['*.es']

    flags = re.MULTILINE

    tokens = {
        'root': [
            (r'//.*', Comment.Single),
            (r'(?i)(GET|POST|PUT|DELETE)\b', Keyword, 'api_path'),
            (VARIABLE_PATTERN, Variable, 'func_args'),
            # TODO: more keywords
            (r'\s+', Whitespace),
        ],
        'api_path': [
            (r'(' + W + r'*)(\S+)', bygroups(Whitespace, Literal), ('#pop', 'opts')),
        ],
        'opts': [
            DoubleNLPop,
            (r'\n', Whitespace, ('#pop', 'payload')),
            (r'//.*', Comment.Single),
            (r'(' + VARIABLE_PATTERN + r')(' + W + r'*)(=)(' + W + r'*)',
             bygroups(Name, Whitespace, Assign, Whitespace), 'expr'),
            (W + r'+', Whitespace),
        ],
        'expr': [
            # Name, Value and expression
            (VARIABLE_PATTERN, Name),
            include('value'),
            default('#pop'),
        ],
        'payload': [
            DoubleNLPop,
            (r'(//.*)(\n)', bygroups(Comment.Single, Whitespace)),
            (r'(\n' + W + r'*)(?={)', Whitespace, 'dict'),
            (r'(' + W + r'*)(?={)', Whitespace, 'dict'),
            default('#pop'),
        ],

        'func_args': [
            (r'\n', BlankLine, '#pop'),
            (r'//.*', Comment.Single),
            (r'(' + VARIABLE_PATTERN + r')(' + W + r'*)(=)(' + W + r'*)',
             bygroups(Name, Whitespace, Assign, Whitespace), 'expr'),
            (VARIABLE_PATTERN, Name),
            include('value'),
            (W + r'+', Whitespace),
            default('#pop'),
        ],
        'dict': [
            (r'({)(\s*)', bygroups(CurlyLeft, Whitespace), 'dict_key'),
            (r'//.*', Comment.Single),
            (r'\s+', Whitespace),
            (r'}', CurlyRight, '#pop'),
            (r'(,)(\s*)', bygroups(Comma, Whitespace), 'dict_key'),
        ],
        'dict_key': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            (r'"', PayloadKey, 'dqs_key'),
            (r"'", PayloadKey, 'sqs_key'),
            (r'(\s*)(:)(\s*)', bygroups(Whitespace, Colon, Whitespace), ('#pop', 'dict_value')),
            default('#pop'),
        ],
        'dict_value': [
            (r'(\s*)(//.*)(\s*)', bygroups(Whitespace, Comment.Single, Whitespace)),
            include('expr'),
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
            include('expr'),
        ],
        'value': [
            (r'(' + W + r'*)(?={)', Whitespace, 'dict'),
            (r'(' + W + r'*)(?=\[)', Whitespace, 'array'),
            (r'"""', TripleD, 'tdqs'),
            (r"'''", TripleS, 'tsqs'),
            (r'"', String.Double, 'dqs'),
            (r"'", String.Single, 'sqs'),
            (words(('true', 'false', 'null'), suffix=r'\b'), Name.Builtin),
            include('numbers'),
        ],
        'dqs_key': dqs(PayloadKey),
        'sqs_key': sqs(PayloadKey),
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
            (r'[-+]?(\d+\.\d*|\d*\.\d+)([eE][+-]?[0-9]+)?j?', Number.Float),
            (r'[-+]?\d+[eE][+-]?[0-9]+j?', Number.Float),
            (r'[-+]?0[0-7]+j?', Number.Oct),
            (r'[-+]?0[bB][01]+', Number.Bin),
            (r'[-+]?0[xX][a-fA-F0-9]+', Number.Hex),
            (r'[-+]?\d+L', Number.Integer.Long),
            (r'[-+]?\d+j?', Number.Integer),
        ],
    }

    def __init__(self, stack=None, **options):
        super().__init__(**options)
        self.stack = stack or ('root',)

    def get_tokens_unprocessed(self, text, stack=None) -> PeekToken:
        stack = stack or self.stack
        for t in super().get_tokens_unprocessed(text, stack):
            yield PeekToken(*t)
