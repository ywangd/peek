import logging

from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import ValidationState, Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition, completion_is_selected, is_searching, has_completions
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent

from peek.common import HTTP_METHODS
from peek.errors import PeekSyntaxError, PeekError
from peek.lexers import PeekLexer, TripleD, TripleS, ParenLeft, BracketLeft, CurlyLeft, ParenRight, BracketRight, \
    CurlyRight
from peek.parser import process_tokens
from peek.visitors import FormattingVisitor

_logger = logging.getLogger(__name__)


def key_bindings(app):
    kb = KeyBindings()

    @kb.add('tab', filter=~(completion_is_selected | is_searching | has_completions))
    def _(event):
        event.current_buffer.insert_text('  ')

    @kb.add('enter', filter=~(completion_is_selected | is_searching) & buffer_should_be_handled(app))
    def _(event):
        event.current_buffer.validate_and_handle()
        if app.capture.file() is not None:
            print(event.current_buffer.text, file=app.capture.file())

    @kb.add('enter', filter=~(completion_is_selected | is_searching) & ~buffer_should_be_handled(app))
    def _(event):
        b = event.current_buffer  # type: Buffer
        c = b.document.current_char

        # When cursor is on the right curly bracket, just use the ident of the current line
        existing_indent = 0
        for x in b.document.current_line:
            if x.isspace():
                existing_indent += 1
            else:
                break
        if c in ('}', ']'):
            b.insert_text('\n' + ' ' * (existing_indent + 2))
            b.insert_text('\n' + ' ' * existing_indent, move_cursor=False)
        else:
            b.insert_text('\n' + ' ' * existing_indent)

    @kb.add("enter", filter=completion_is_selected)
    def _(event):
        event.current_buffer.complete_state = None
        event.app.current_buffer.complete_state = None

    @kb.add('escape', 'enter', filter=~(completion_is_selected | is_searching))
    def _(event):
        event.current_buffer.validate_and_handle()
        if app.capture.file() is not None:
            print(event.current_buffer.text, file=app.capture.file())

    @kb.add('escape', 'c')
    def _(event: KeyPressEvent):
        get_app().clipboard.set_text(event.app.current_buffer.text)
        app.preserved_text = event.current_buffer.text
        event.current_buffer.reset()
        event.current_buffer.validate_and_handle()

    @kb.add('escape', 'a')
    def _(event: KeyPressEvent):
        event.current_buffer.cursor_position = 0

    @kb.add('escape', 'e')
    def _(event: KeyPressEvent):
        event.current_buffer.cursor_position = len(event.current_buffer.text)

    @kb.add('c-d')
    def _(event):
        app.signal_exit()
        # Short circuit the validation
        event.current_buffer.validation_state = ValidationState.VALID
        event.current_buffer.validate_and_handle()

    @kb.add("c-space")
    def _(event):
        b = event.app.current_buffer
        if b.complete_state:
            b.complete_next()
        else:
            b.start_completion(select_first=False)

    @kb.add('f3')
    def _(event):
        _logger.debug('Reformatting payload json')
        try:
            texts = []
            nodes = app.parser.parse(event.current_buffer.text)
            for j, node in enumerate(nodes):
                texts.append(FormattingVisitor(pretty=app.is_pretty).visit(node))
            event.current_buffer.text = '\n'.join(texts)
            app.is_pretty = not app.is_pretty
        except PeekSyntaxError as e:
            _logger.debug(f'Cannot reformat for invalid/incomplete input: {e}')

    @kb.add('f12')
    def _(event):
        _logger.debug('Toggle mouse support')
        app.config['mouse_support'] = not app.config.as_bool('mouse_support')

    def switch_connection(event):
        _logger.debug(f'switching to connection: {event.key_sequence[1].key}')
        try:
            app.es_client_manager.set_current(int(event.key_sequence[1].key))
            app.preserved_text = event.current_buffer.text
            event.current_buffer.reset()
            event.current_buffer.validate_and_handle()
        except PeekError as e:
            app.display.error(e)

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
    peek_lexer = PeekLexer()

    @Condition
    def cond():
        document: Document = get_app().layout.get_buffer_by_name(DEFAULT_BUFFER).document
        _logger.debug(f'current document: {document}')
        # Always handle empty text
        if document.text.strip() == '':
            return True

        if document.line_count == 1:
            if document.text.strip().split(maxsplit=1)[0].lower() in (HTTP_METHODS + ['for']):
                return False
            else:
                tokens = process_tokens(peek_lexer.get_tokens_unprocessed(document.text_before_cursor))
                if len(tokens) == 0:  # cursor is at the very beginning
                    return True
                last_token = tokens[-1]
                if last_token.ttype in (TripleS, TripleD):
                    remainder = last_token.value[3:][-3:]
                    text = remainder + document.text_after_cursor
                    marker = '"""' if last_token.ttype is TripleD else "'''"
                    for i in range(min(len(remainder), 3)):
                        if text[i:i + 3] == marker:
                            return True
                    _logger.debug('Cursor is inside triple quotes')
                    return False
                balance = 0
                for t in tokens:
                    if t.ttype in (ParenLeft, BracketLeft, CurlyLeft):
                        balance -= 1
                    elif t.ttype in (ParenRight, BracketRight, CurlyRight):
                        balance += 1

                if balance < 0:
                    _logger.debug('Cursor is inside brackets')
                    return False
                else:
                    return True
        else:
            if document.current_line.strip() == '' and document.text_after_cursor.strip() == '':
                _logger.debug('lines are empty at and after cursor')
                return True
            else:
                return False

    return cond
