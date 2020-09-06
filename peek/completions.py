import logging
from typing import Tuple

from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.completion import Completion

_logger = logging.getLogger(__name__)


def proxy_new_text_and_position(self) -> Tuple[str, int]:
    _logger.warning('proxying!!!!!!')
    new_text, new_cursor_position = self.original_new_text_and_position()
    if self.complete_index is None:
        return new_text, new_cursor_position

    c = self.completions[self.complete_index]
    if isinstance(c, PayloadKeyTemplateCompletion):
        # check whether original text and cursor is something like "CURSOR"
        # Optionally check whether new text is followed by a quote
        # remove the quote
        mod_text = new_text
        return mod_text, new_cursor_position
    else:
        return new_text, new_cursor_position


def completion_monkey_patch():
    if CompletionState.new_text_and_position != proxy_new_text_and_position:
        setattr(CompletionState, 'original_new_text_and_position', CompletionState.new_text_and_position)
        setattr(CompletionState, 'new_text_and_position', proxy_new_text_and_position)


class PayloadKeyTemplateCompletion(Completion):
    pass
