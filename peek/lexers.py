import re

from pygments.lexer import RegexLexer, words, include, bygroups, using
from pygments.style import Style
from pygments.token import Keyword, Literal, String, Number, Punctuation, Name, Comment, Whitespace


# null: #445

class PeekStyle(Style):
    default_style = ''
    styles = {
        Keyword: '#d38',
        Literal: '#499',
        String.Symbol: '#bff',  # '#28b',
        String: '#395',
        Name.Builtin: '#77f',
        Number: '#07a'
    }


def dqs(ttype):
    return [
               (r'"', ttype, '#pop'),
               (r'\\\\|\\"|\\\n', String.Escape),  # included here for raw strings
           ] + innerstring_rules(ttype)


def sqs(ttype):
    return [
               (r"'", ttype, '#pop'),
               (r"\\\\|\\'|\\\n", String.Escape),  # included here for raw strings

           ] + innerstring_rules(ttype)


def innerstring_rules(ttype):
    return [
        # backslashes, quotes and formatting signs must be parsed one at a time
        (r'[^\\\'"%\n]+', ttype),
        (r'[\'"\\]', ttype),
        # newlines are an error (use "nl" state)
    ]


class PayloadLexer(RegexLexer):
    name = 'PAYLOAD'
    aliases = ['payload']

    flags = re.IGNORECASE

    tokens = {
        'root': [
            (r'//.+$', Comment.Single),
            (r'{', Punctuation.Curly.Left, 'dict-key'),
            (r'\s+', Whitespace),
        ],
        'dict-key': [
            (r'//.+$', Comment.Single),
            (r'}', Punctuation.Curly.Right, '#pop'),  # empty dict
            (r'"', String.Symbol, 'dqs-key'),
            (r"'", String.Symbol, 'sqs-key'),
            (r':', Punctuation.Colon, ('#pop', 'dict-value')),
            (r'\s+', Whitespace),
        ],
        'dict-value': [
            (r',', Punctuation.Comma, ('#pop', 'dict-key')),
            (r'}', Punctuation.Curly.Right, '#pop'),
            include('value'),
        ],
        'array-values': [
            (r',', Punctuation.Comma),
            (r']', Punctuation.Bracket.Right, '#pop'),
            include('value'),
        ],
        'value': [
            (r'//.+$', Comment.Single),
            (r'{', Punctuation.Curly.Left, 'dict-key'),
            (r'\[', Punctuation.Bracket.Left, 'array-values'),
            (r'"', String.Double, 'dqs'),
            (r"'", String.Single, 'sqs'),
            (words(('true', 'false', 'null'), suffix=r'\b'), Name.Builtin),
            include('numbers'),
            (r'\s+', Whitespace),
        ],
        'dqs-key': dqs(String.Symbol),
        'sqs-key': sqs(String.Symbol),
        'dqs': dqs(String.Double),
        'sqs': dqs(String.Single),
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
            (r'\s+', Whitespace),
            (r'//.+$', Comment.Single),
            (words(('GET', 'POST', 'PUT', 'DELETE'), suffix=r'\b'), Keyword, ('#pop', 'path')),
            (r'^(\s*)(%)', bygroups(Whitespace, Punctuation.Percent), ('#pop', 'command')),
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
            (r'//.+$', Comment.Single),
            (r'\S+', Literal),
            (r'\s+', Whitespace),
        ],
    }
