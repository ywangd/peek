import logging
import os

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings

_logger = logging.getLogger(__name__)


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


def buffer_should_be_handled(repl):
    @Condition
    def cond():
        if repl.state_new_command:
            return True

        doc = get_app().layout.get_buffer_by_name(DEFAULT_BUFFER).document
        _logger.debug(f'current doc: {doc}')
        # Handle the command when an empty line is entered
        last_linesep_position = doc.text.rfind(os.linesep)
        if last_linesep_position != -1 and doc.text[last_linesep_position:].strip() == '':
            return True

        return False

    return cond
