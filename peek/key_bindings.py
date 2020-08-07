import logging
import os

from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import ValidationState
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition, completion_is_selected, is_searching
from prompt_toolkit.key_binding import KeyBindings

from peek.common import HTTP_METHODS
from peek.errors import PeekSyntaxError, PeekError
from peek.visitors import FormattingVisitor

_logger = logging.getLogger(__name__)


def key_bindings(app):
    kb = KeyBindings()

    @kb.add('enter', filter=~(completion_is_selected | is_searching) & buffer_should_be_handled(app))
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add('escape', 'enter', filter=~(completion_is_selected | is_searching))
    def _(event):
        event.app.current_buffer.newline()

    @kb.add('c-d')
    def _(event):
        app.signal_exit()
        # Short circuit the validation
        event.current_buffer.validation_state = ValidationState.VALID
        event.current_buffer.validate_and_handle()

    @kb.add('f3')
    def _(event):
        _logger.debug('Reformatting payload json')
        try:
            texts = []
            for node in app.parser.parse(event.current_buffer.text):
                texts.append(FormattingVisitor(pretty=app.is_pretty).visit(node))
            event.current_buffer.text = ''.join(texts)
            app.is_pretty = not app.is_pretty
        except PeekSyntaxError as e:
            _logger.debug(f'Cannot reformat for invalid/incomplete input: {e}')

    def switch_connection(event):
        _logger.debug(f'switching to connection: {event.key_sequence[1].key}')
        try:
            app.es_client_manager.current = int(event.key_sequence[1].key)
            app.preserved_text = event.current_buffer.text
            event.current_buffer.reset()
            event.current_buffer.validate_and_handle()
        except PeekError as e:
            app.display.show(e)

    for i in range(5):
        kb.add('escape', f'{i}')(switch_connection)

    # par-editing is a shamelessly copy from https://github.com/nicolewhite/cycli/blob/master/cycli/binder.py
    @kb.add("{")
    def curly_left(event):
        b = event.current_buffer
        b.insert_text("{")
        b.insert_text("}", move_cursor=False)

    @kb.add("}")
    def curly_right(event):
        b = event.current_buffer
        char = b.document.current_char

        if char == "}":
            b.cursor_right()
        else:
            b.insert_text("}")

    @kb.add("(")
    def paren_left(event):
        b = event.current_buffer
        b.insert_text("(")
        b.insert_text(")", move_cursor=False)

    @kb.add(")")
    def paren_right(event):
        b = event.current_buffer
        char = b.document.current_char

        if char == ")":
            b.cursor_right()
        else:
            b.insert_text(")")

    @kb.add("[")
    def bracket_left(event):
        b = event.current_buffer
        b.insert_text("[")
        b.insert_text("]", move_cursor=False)

    @kb.add("]")
    def bracket_right(event):
        b = event.current_buffer
        char = b.document.current_char

        if char == "]":
            b.cursor_right()
        else:
            b.insert_text("]")

    @kb.add("'")
    def apostrophe(event):
        b = event.current_buffer
        char = b.document.current_char

        if char == "'":
            b.cursor_right()
        else:
            b.insert_text("'")
            b.insert_text("'", move_cursor=False)

    @kb.add("\"")
    def quote(event):
        b = event.current_buffer
        char = b.document.current_char

        if char == "\"":
            b.cursor_right()
        else:
            b.insert_text("\"")
            b.insert_text("\"", move_cursor=False)

    @kb.add("`")
    def backtick(event):
        b = event.current_buffer
        char = b.document.current_char

        if char == "`":
            b.cursor_right()
        else:
            b.insert_text("`")
            b.insert_text("`", move_cursor=False)

    @kb.add('c-h')  # backspace
    def backspace(event):
        b = event.current_buffer
        current_char = b.document.current_char
        before_char = b.document.char_before_cursor

        patterns = [("(", ")"), ("[", "]"), ("{", "}"), ("'", "'"), ('"', '"'), ("`", "`")]

        for pattern in patterns:
            if before_char == pattern[0] and current_char == pattern[1]:
                b.cursor_right()
                b.delete_before_cursor(2)
                return

        b.delete_before_cursor()

    return kb


def buffer_should_be_handled(app):
    @Condition
    def cond():
        doc = get_app().layout.get_buffer_by_name(DEFAULT_BUFFER).document
        _logger.debug(f'current doc: {doc}')
        if doc.text.strip() == '':
            return True
        elif doc.text.lstrip().split(maxsplit=1)[0].upper() not in HTTP_METHODS:
            return True

        # Handle ES API call when an empty line is entered
        last_linesep_position = doc.text.rfind(os.linesep)
        if last_linesep_position != -1 and doc.text[last_linesep_position:].strip() == '':
            return True

        return False

    return cond
