import re

from pygments.lexer import RegexLexer, words, include, bygroups
from pygments.style import Style
from pygments.token import Keyword, Literal, String, Number, Text, Punctuation, Name, Comment, Whitespace


# null: #445

class PeekStyle(Style):
    default_style = ''
    styles = {
        Keyword: '#d38',
        Literal: '#499',
        String.Symbol: '#28b',
        String: '#395',
        Name.Builtin: '#77f',
        Number: '#07a'
    }


def innerstring_rules(ttype):
    return [
        # backslashes, quotes and formatting signs must be parsed one at a time
        (r'[^\\\'"%\n]+', ttype),
        (r'[\'"\\]', ttype),
        # newlines are an error (use "nl" state)
    ]


class PeekLexer(RegexLexer):
    name = 'ES'
    aliases = ['es']
    filenames = ['*.es']

    flags = re.IGNORECASE

    tokens = {
        'root': [
            (r'\s+', Whitespace),
            (words(('GET', 'POST', 'PUT', 'DELETE'), suffix=r'\b'), Keyword, 'path'),
            (r'^(\s*)(%)(\S+)',
             bygroups(Whitespace, Name.Symbol, Name.Builtin), 'args')
        ],
        'path': [
            (r'\s+', Whitespace),
            (r'\S+', Literal, 'payload')
        ],
        'payload': [
            (words(('true', 'false', 'null'), suffix=r'\b'), Name.Builtin),
            (r'//.+$', Comment.Single),
            (r'[]{}:,[]', Punctuation),
            ('"', String.Double, 'dqs'),
            ("'", String.Single, 'sqs'),
            include('numbers'),
            (r'\s+', Whitespace),
        ],
        'strings-double': innerstring_rules(String.Double),
        'strings-single': innerstring_rules(String.Single),
        'dqs': [
            (r'"', String.Double, '#pop'),
            (r'\\\\|\\"|\\\n', String.Escape),  # included here for raw strings
            include('strings-double')
        ],
        'sqs': [
            (r"'", String.Single, '#pop'),
            (r"\\\\|\\'|\\\n", String.Escape),  # included here for raw strings
            include('strings-single')
        ],
        'numbers': [
            (r'(\d+\.\d*|\d*\.\d+)([eE][+-]?[0-9]+)?j?', Number.Float),
            (r'\d+[eE][+-]?[0-9]+j?', Number.Float),
            (r'0[0-7]+j?', Number.Oct),
            (r'0[bB][01]+', Number.Bin),
            (r'0[xX][a-fA-F0-9]+', Number.Hex),
            (r'\d+L', Number.Integer.Long),
            (r'\d+j?', Number.Integer)
        ],
        'args': [
            (r'\s+', Whitespace),
            (r'\S+', Literal),
        ],
    }
