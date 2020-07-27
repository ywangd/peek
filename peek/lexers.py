import re

from pygments.lexer import RegexLexer, words, include, bygroups, using
from pygments.style import Style
from pygments.token import Keyword, Literal, String, Number, Punctuation, Name, Comment, Whitespace, Generic

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


class PeekStyle(Style):
    default_style = ''
    # null: #445
    styles = {
        Keyword: '#d38',
        Literal: '#FFFCF9',
        String.Symbol: '#bff',  # '#28b',
        String: '#395',
        Name.Builtin: '#77f',
        Number: '#07a',
        Heading: '#F6D845',
    }


def dqs(ttype):
    return [
        (r'"', ttype, '#pop'),
        (r'\\\\|\\"|\\', ttype),  # allow escapes
        (r'[^\\\n"]+', ttype),  # not cater for multiple line
    ]


def sqs(ttype):
    return [
        (r"'", ttype, '#pop'),
        (r"\\\\|\\'|\\", ttype),  # allow escapes
        (r'[^\\\n\']+', ttype),  # not cater for multiple line
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
            (r'"', String.Symbol, 'dqs-key'),
            (r"'", String.Symbol, 'sqs-key'),
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
        'dqs-key': dqs(String.Symbol),
        'sqs-key': sqs(String.Symbol),
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

    flags = re.IGNORECASE

    tokens = {
        'root': [
            (r'//.*', Comment.Single),
            (r'\s+', Whitespace),
            (words(('GET', 'POST', 'PUT', 'DELETE'), suffix=r'\b'), Keyword, ('#pop', 'path')),
            (r'^(\s*)(%)', bygroups(Whitespace, Percent), ('#pop', 'command')),
        ],
        'path': [
            (r'\s+', Whitespace),
            (r'\S+', Literal, ('#pop', 'payload')),
        ],
        'payload': [
            (r'(?s)(.*)', bygroups(using(PayloadLexer)), '#pop'),
        ],
        'command': [
            (r'\S+', Name.Builtin, ('#pop', 'args')),
            (r'\s+', Whitespace),
        ],
        'args': [
            (r'//.*', Comment.Single),
            (r'\S+', Literal),
            (r'\s+', Whitespace),
        ],
    }
