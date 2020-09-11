from unittest.mock import MagicMock

from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document

from peek.completions import proxy_new_text_and_position, monkey_patch_completion_state, PayloadKeyCompletion

monkey_patch_completion_state()


def test_complete_will_delegate_when_complete_index_is_none():
    completion_state = MagicMock()
    completion_state.complete_index = None
    proxy_new_text_and_position(completion_state)
    completion_state.original_new_text_and_position.assert_called_once()


def test_complete_will_delegate_when_completion_is_not_payload_key():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [Completion('foo')]
    proxy_new_text_and_position(completion_state)
    completion_state.original_new_text_and_position.assert_called_once()


def test_complete_dict():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [PayloadKeyCompletion('key', {'foo': [], 'bar': ''})]
    completion_state.original_document = Document('{ ""', cursor_position=3)
    assert proxy_new_text_and_position(completion_state) == ('{ "key": {}, ', 10)


def test_complete_array():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [PayloadKeyCompletion('key', ['foo'])]
    completion_state.original_document = Document('{ ""', cursor_position=3)
    assert proxy_new_text_and_position(completion_state) == ('{ "key": [], ', 10)


def test_complete_array_of_dict():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [PayloadKeyCompletion('key', [{'foo': 'bar'}])]
    completion_state.original_document = Document('{ ""', cursor_position=3)
    assert proxy_new_text_and_position(completion_state) == ('''{ "key": [
  {}
], ''', 14)


def test_complete_one_of():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [PayloadKeyCompletion('key', {'__one_of': ['true', 'false']})]
    completion_state.original_document = Document('{ ""', cursor_position=3)
    assert proxy_new_text_and_position(completion_state) == ('{ "key": "true", ', 10)


def test_complete_template():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [PayloadKeyCompletion('key', {'__template': {'foo': [], 'bar': 'hello'}})]
    completion_state.original_document = Document('{ ""', cursor_position=3)
    assert proxy_new_text_and_position(completion_state) == ('''{ "key": {
  "foo": [],
  "bar": "hello"
}, ''', 21)


def test_complete_template_indent():
    completion_state = MagicMock()
    completion_state.complete_index = 0
    completion_state.completions = [PayloadKeyCompletion('key', {'__template': {'foo': {'bar': 42}, 'fizz': 'hello'}})]
    completion_state.original_document = Document('''{
  'foo': {
    ''
  }
}''', cursor_position=18)
    # TODO: the cursor position is not really right.it's inside "bar".
    assert proxy_new_text_and_position(completion_state) == ('''{
  'foo': {
    "key": {
      "foo": {
        "bar": 42
      },
      "fizz": "hello"
    }, \n  }
}''', 50)
