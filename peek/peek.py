"""Main module."""
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import style_from_pygments_cls
from prompt_toolkit.lexers import PygmentsLexer

from pygments.styles.default import DefaultStyle
from pygments.lexers.javascript import JavascriptLexer

kb = KeyBindings()
# @kb.add('c-d')
# def _(event):
#     pass

class Repl:

    def __init__(self):
        self.session = PromptSession(key_bindings=kb)
        self.state_payload = False

    def run(self):
        while True:
            try:
                self._loop()
            except EOFError:
                exit(0)

    def _loop(self):
        source = self.session.prompt(
            '', lexer=PygmentsLexer(JavascriptLexer),
            style=style_from_pygments_cls(DefaultStyle),
            multiline=self.state_payload,
        )
        print(f'You typed: {type(source)} {source}')
        self.state_payload = not self.state_payload
