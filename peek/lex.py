import re

from pygments.lexer import RegexLexer, words, include
from pygments.token import Name, Keyword, Literal, Punctuation, String, Number, Text


class EsLexer(RegexLexer):
    name = 'ES'
    aliases = ['es']
    filenames = ['*.es']

    flags = re.IGNORECASE | re.DOTALL

    def innerstring_rules(ttype):
        return [
            # the old style '%s' % (...) string formatting
            (r'%(\(\w+\))?[-#0 +]*([0-9]+|[*])?(\.([0-9]+|[*]))?'
             '[hlL]?[E-GXc-giorsux%]', String.Interpol),
            # backslashes, quotes and formatting signs must be parsed one at a time
            (r'[^\\\'"%\n]+', ttype),
            (r'[\'"\\]', ttype),
            # unhandled string formatting sign
            (r'%', ttype),
            # newlines are an error (use "nl" state)
        ]

    tokens = {
        'root': [
            (words(('GET', 'POST', 'PUT', 'DELETE'), suffix=r'\b'), Keyword, 'path'),
        ],
        'path': [
            (r'\s+', Literal, 'payload'),
        ],
        'payload': [
            # (r'\{', Punctuation),
            (words(('true', 'false'), suffix=r'\b'), Keyword.Constant),
            ('"', String.Double, 'dqs'),
            ("'", String.Single, 'sqs'),
            include('numbers'),
            # (r'[^\S\n]+', Text),
            (r'\s+', Literal),

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
    }

