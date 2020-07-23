"""Main module."""
import logging

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import style_from_pygments_cls
from prompt_toolkit.lexers import PygmentsLexer

from pygments.styles.default import DefaultStyle
from pygments.lexers.javascript import JavascriptLexer

_logger = logging.getLogger(__name__)


def buffer_should_be_handled(repl):
    @Condition
    def cond():
        if not repl.state_payload:
            return True

        doc = get_app().layout.get_buffer_by_name(DEFAULT_BUFFER).document
        # Handle the command when an empty line is entered
        if doc.text.endswith('\n'):
            return True

        return False
    return cond


def key_bindings(repl):
    kb = KeyBindings()

    @kb.add("enter", filter=buffer_should_be_handled(repl))
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-d")
    def _(event):
        repl.signal_exit()
        event.current_buffer.validate_and_handle()

    return kb


class Repl:

    def __init__(self):
        self.state_payload = False
        self._should_exit = False
        self.session = PromptSession(
            message=self._get_message(),
            prompt_continuation='  ',
            style=style_from_pygments_cls(DefaultStyle),
            lexer=PygmentsLexer(JavascriptLexer),
            multiline=True,
            key_bindings=key_bindings(self),
            enable_open_in_editor=True,
            enable_system_prompt=True,
            enable_suspend=True,
            search_ignore_case=True
        )

    def run(self):
        try:
            while True:
                source = self.session.prompt()
                if self._should_exit:
                    raise EOFError()
                print(f'You typed: {type(source)} {source}')
                self.state_payload = not self.state_payload
        except EOFError:
            pass

    def signal_exit(self):
        self._should_exit = True

    def _get_message(self):
        return '  ' if self.state_payload else '> '
