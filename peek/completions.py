import json
import logging
from typing import Tuple

from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.completion import Completion

_logger = logging.getLogger(__name__)


def proxy_new_text_and_position(self: CompletionState) -> Tuple[str, int]:
    _logger.warning('proxying!!!!!!')
    if self.complete_index is None:
        return self.original_new_text_and_position()

    c = self.completions[self.complete_index]
    if not isinstance(c, PayloadKeyCompletion):
        return self.original_new_text_and_position()

    # check whether original text and cursor is something like "CURSOR"
    # Optionally check whether new text is followed by a quote
    # remove the quote

    original_text_before_cursor = self.original_document.text_before_cursor
    original_text_after_cursor = self.original_document.text_after_cursor

    _logger.debug(f'text_before_cursor: {original_text_before_cursor!r}')
    _logger.debug(f'start_position: {c.start_position!r}')
    end_position = len(original_text_before_cursor) if c.start_position == 0 else c.start_position
    quote = original_text_before_cursor[end_position - 3:end_position]
    _logger.debug(f'quote: {quote!r}')
    if quote not in ('"""', "'''"):
        quote = quote[-1]

    idx_quote_end = original_text_after_cursor.find(quote)
    if idx_quote_end == -1:
        idx_quote_end = original_text_after_cursor.find('\n')
        if idx_quote_end == -1:
            idx_quote_end = len(original_text_after_cursor) - 1
    idx_quote_end += 1

    before = original_text_before_cursor[: c.start_position - len(quote)]

    current_indent = len(self.original_document.current_line) - len(self.original_document.current_line.lstrip())

    key_fill = f'{json.dumps(c.text)}: '
    # TODO: Indent of last line is incorrect
    # TODO: actually indent is all wrong
    if isinstance(c.value, dict):
        if '__template' in c.value:
            value_fill = json.dumps(c.value['__template'], indent=current_indent + 2)
        else:
            value_fill = '{}'
    elif isinstance(c.value, list):
        if len(c.value) > 0:
            value_fill = json.dumps([{}], indent=current_indent + 2)
        else:
            value_fill = '[]'
    elif isinstance(c.value, str):
        value_fill = json.dumps(c.value)
    else:
        value_fill = str(c.value)

    value_fill += ', '

    before = before + key_fill
    new_text = before + value_fill + original_text_after_cursor[idx_quote_end:]

    for idx, c in enumerate(value_fill):
        if c in (']', ')', '}'):
            new_cursor_position = len(before) + idx
            break
        elif c in ('"', "'"):
            new_cursor_position = len(before) + idx + 1
            break
        elif c == ',':
            new_cursor_position = len(before) + idx - 1
            break
    else:
        new_cursor_position = len(before)

    # TODO: Remove completion menu
    return new_text, new_cursor_position


def completion_monkey_patch():
    if CompletionState.new_text_and_position != proxy_new_text_and_position:
        setattr(CompletionState, 'original_new_text_and_position', CompletionState.new_text_and_position)
        setattr(CompletionState, 'new_text_and_position', proxy_new_text_and_position)


class PayloadKeyCompletion(Completion):

    def __init__(self, text: str, value, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.value = value
