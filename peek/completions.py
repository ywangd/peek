import json
import logging
from typing import Tuple, Any

from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.completion import Completion

_logger = logging.getLogger(__name__)


class PayloadKeyCompletion(Completion):

    def __init__(self, text: str, value, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.value = value


def proxy_new_text_and_position(self: CompletionState) -> Tuple[str, int]:
    if self.complete_index is None:
        return self.original_new_text_and_position()

    c = self.completions[self.complete_index]
    if not isinstance(c, PayloadKeyCompletion):
        return self.original_new_text_and_position()

    # check whether original text and cursor is something like "CURSOR"
    # Optionally check whether new text is followed by a quote and
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
    value_fill = get_value_fill(c.value, current_indent)

    before = before + key_fill
    new_text = before + value_fill + original_text_after_cursor[idx_quote_end:]

    seen_left_curly = False
    seen_quote = 0
    for idx, c in enumerate(value_fill):
        if c == '{':
            seen_left_curly = True

        if c in (']', ')', '}'):
            new_cursor_position = len(before) + idx
            break
        elif c in ('"', "'"):
            if not seen_left_curly or (seen_left_curly and seen_quote >= 2):
                new_cursor_position = len(before) + idx + 1
                break
            else:
                seen_quote += 1
        elif c == ',':
            new_cursor_position = len(before) + idx - 1
            break
    else:
        new_cursor_position = len(before)

    return new_text, new_cursor_position


def get_value_fill(value: Any, current_indent: int):
    if isinstance(value, dict):
        if '__template' in value:
            value_fill = serialise_and_indent_json(value['__template'], current_indent)
        elif '__one_of' in value:
            return get_value_fill(value['__one_of'][0], current_indent)
        else:
            value_fill = '{}'
    elif isinstance(value, list):
        if len(value) > 0 and isinstance(value[0], dict):
            value_fill = serialise_and_indent_json([{}], current_indent)
        else:
            value_fill = '[]'
    else:
        value_fill = json.dumps(value)

    value_fill += ', '

    return value_fill


def serialise_and_indent_json(data, current_indent):
    indent = current_indent * ' '
    res = json.dumps(data, indent=2)
    return res.replace('\n', f'\n{indent}')


def monkey_patch_completion_state():
    if CompletionState.new_text_and_position != proxy_new_text_and_position:
        setattr(CompletionState, 'original_new_text_and_position', CompletionState.new_text_and_position)
        setattr(CompletionState, 'new_text_and_position', proxy_new_text_and_position)
