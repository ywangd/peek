"""Main module."""
from prompt_toolkit import prompt
from prompt_toolkit.styles import style_from_pygments_cls
from prompt_toolkit.lexers import PygmentsLexer

from pygments.styles.default import DefaultStyle
from pygments.lexers.javascript import JavascriptLexer


class Repl:

    def __init__(self):
        pass

    def run(self):
        source = prompt('', lexer=PygmentsLexer(JavascriptLexer), style=style_from_pygments_cls(DefaultStyle))
        print(f'You typed: {source}')
