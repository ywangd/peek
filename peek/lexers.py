import re

from pygments.lexer import RegexLexer, words, include, bygroups, using
from pygments.style import Style
from pygments.token import Keyword, Literal, String, Number, Punctuation, Name, Comment, Whitespace, Generic, Error

HTTP_METHODS = ('GET', 'POST', 'PUT', 'DELETE')

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
BlankLine = Whitespace.BlankLine
SpecialFunc = Name.SpecialFunc
PayloadKey = String.Symbol
EOF = Whitespace.EOF


class PeekStyle(Style):
    default_style = ''
    # null: #445
    styles = {
        Keyword: '#03F147',
        Literal: '#FFFCF9',
        PayloadKey: '#bff',  # '#28b',
        String: '#395',
        Name.Builtin: '#77f',
        SpecialFunc: '#77f',
        Number: '#07a',
        Heading: '#F6D845',
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


class PayloadLexer(RegexLexer):
    name = 'PAYLOAD'
    aliases = ['payload']

    flags = re.MULTILINE

    tokens = {
        'root': [
            (r'//.*', Comment.Single),
            (r'{', CurlyLeft, 'dict-key'),
            (r'\s+', Whitespace),
        ],
        'dict-key': [
            (r'//.*', Comment.Single),
            (r'}', CurlyRight, '#pop'),  # empty dict
            (r'"', PayloadKey, 'dqs-key'),
            (r"'", PayloadKey, 'sqs-key'),
            (r':', Colon, ('#pop', 'dict-value')),
            (r'\s+', Whitespace),
        ],
        'dict-value': [
            (r',', Comma, ('#pop', 'dict-key')),
            (r'}', CurlyRight, '#pop'),
            include('value'),
        ],
        'array-values': [
            (r',', Comma),
            (r']', BracketRight, '#pop'),
            include('value'),
        ],
        'value': [
            (r'//.*', Comment.Single),
            (r'{', CurlyLeft, 'dict-key'),
            (r'\[', BracketLeft, 'array-values'),
            (r'"""', TripleD, 'tdqs'),
            (r"'''", TripleS, 'tsqs'),
            (r'"', String.Double, 'dqs'),
            (r"'", String.Single, 'sqs'),
            (words(('true', 'false', 'null'), suffix=r'\b'), Name.Builtin),
            include('numbers'),
            (r'\s+', Whitespace),
        ],
        'dqs-key': dqs(PayloadKey),
        'sqs-key': sqs(PayloadKey),
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
            (r'(\d+\.\d*|\d*\.\d+)([eE][+-]?[0-9]+)?j?', Number.Float),
            (r'\d+[eE][+-]?[0-9]+j?', Number.Float),
            (r'0[0-7]+j?', Number.Oct),
            (r'0[bB][01]+', Number.Bin),
            (r'0[xX][a-fA-F0-9]+', Number.Hex),
            (r'\d+L', Number.Integer.Long),
            (r'\d+j?', Number.Integer),
        ],
    }


class PeekLexer(RegexLexer):
    name = 'ES'
    aliases = ['es']
    filenames = ['*.es']

    flags = re.MULTILINE

    tokens = {
        'root': [
            (r'//.*', Comment.Single),
            (r'\s+', Whitespace),
            (words(HTTP_METHODS, prefix=r'(?i)', suffix=r'\b'), Keyword, ('#pop', 'path')),
            (r'^(\s*)(%)', bygroups(Whitespace, Percent), ('#pop', 'command')),
        ],
        'path': [
            (r'\s+', Whitespace),
            (r'\S+', Literal, ('#pop', 'payload')),
        ],
        'payload': [
            (r'(?s)(.*?)(\n\s*\n)', bygroups(using(PayloadLexer), BlankLine), '#pop'),
            (r'(?s)(.*)', bygroups(using(PayloadLexer)), '#pop'),
        ],
        'command': [
            (r'\S+', SpecialFunc, ('#pop', 'args')),
            (r'\s+', Whitespace),
        ],
        'args': [
            (r'\n', BlankLine, '#pop'),
            (r'//.*', Comment.Single),
            (r'\S+', Literal),
            (r'\s+', Whitespace),
        ],
    }
