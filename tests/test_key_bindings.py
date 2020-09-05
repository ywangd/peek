from unittest.mock import patch, MagicMock

from prompt_toolkit.document import Document

from peek.key_bindings import buffer_should_be_handled

mock_app = MagicMock()
layout = MagicMock(name='layout')
buffer = MagicMock(name='buffer')
layout.get_buffer_by_name = MagicMock(return_value=buffer)
app = MagicMock()
app.layout = layout
get_app = MagicMock(return_value=app)


@patch('peek.key_bindings.get_app', get_app)
def test_buffer_will_be_handled_if_it_is_blank():
    buffer.document = Document('')
    assert buffer_should_be_handled(mock_app)() is True

    buffer.document = Document('     ')
    assert buffer_should_be_handled(mock_app)() is True

    buffer.document = Document('     \n  \n \n  ')
    assert buffer_should_be_handled(mock_app)() is True


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_buffer_will_not_be_handled_if_it_is_http_call():
    buffer.document = Document('get')
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('GET')
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('get /')
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('get / conn=1')
    assert buffer_should_be_handled(mock_app)() is False

    for c in range(0, 11):
        buffer.document = Document('get / conn=1', cursor_position=c)
        assert buffer_should_be_handled(mock_app)() is False


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_buffer_will_not_be_handled_if_cursor_is_inside_brackets():
    buffer.document = Document('f 1 3 () 5', cursor_position=7)
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('f 42 a [] 3', cursor_position=8)
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('echo "a" b {}', cursor_position=12)
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('echo "a" b {[()]}', cursor_position=14)
    assert buffer_should_be_handled(mock_app)() is False


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_buffer_will_be_handled_if_cursor_is_inside_simple_quotes():
    buffer.document = Document('echo "abc"', cursor_position=6)
    assert buffer_should_be_handled(mock_app)() is True

    buffer.document = Document("echo 'abc'", cursor_position=7)
    assert buffer_should_be_handled(mock_app)() is True


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_buffer_will_not_be_handled_when_cursor_is_inside_triple_quotes():
    for c in [8, 9, 10, 11]:
        print(c)
        buffer.document = Document('echo """foo"""', cursor_position=c)
        assert buffer_should_be_handled(mock_app)() is False

        buffer.document = Document("echo '''foo'''", cursor_position=c)
        assert buffer_should_be_handled(mock_app)() is False


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_buffer_will_be_handled_when_cursor_is_on_triple_quotes():
    for c in [5, 6, 7, 12, 13, 14]:
        buffer.document = Document('echo """foo"""', cursor_position=c)
        assert buffer_should_be_handled(mock_app)() is True

        buffer.document = Document("echo '''foo'''", cursor_position=c)
        assert buffer_should_be_handled(mock_app)() is True


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_func_stmt_will_be_handled_if_cursor_is_not_within_quotes_or_brackets():
    buffer.document = Document('echo "abc" 1 2 42', cursor_position=0)
    assert buffer_should_be_handled(mock_app)() is True

    for c in range(10, 15):
        buffer.document = Document('echo "abc" 1 2 42', cursor_position=c)
        assert buffer_should_be_handled(mock_app)() is True


@patch('peek.key_bindings.get_app', get_app)
def test_multi_line_buffer_will_be_handled_if_cursor_line_and_all_lines_after_are_blank():
    buffer.document = Document('''echo "foo"
get /

''')
    assert buffer_should_be_handled(mock_app)() is True

    buffer.document = Document('''echo "foo"\nget /\n   ''', cursor_position=18)
    assert buffer_should_be_handled(mock_app)() is True

    buffer.document = Document('''echo "foo"\nget /\n  \n   \n ''', cursor_position=17)
    assert buffer_should_be_handled(mock_app)() is True


@patch('peek.key_bindings.get_app', get_app)
def test_single_line_for_stmt_will_not_be_handled():
    text = '''for i in range(1, 10) {}'''
    for c in range(0, len(text) + 1):
        buffer.document = Document(text)
        assert buffer_should_be_handled(mock_app)() is False


@patch('peek.key_bindings.get_app', get_app)
def test_multi_line_buffer_will_be_not_handled_if_cursor_line_is_not_blank():
    buffer.document = Document('''echo "foo"\nget /\n ''', cursor_position=0)
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('''echo "foo"\nget /\n ''', cursor_position=16)
    assert buffer_should_be_handled(mock_app)() is False

    buffer.document = Document('''echo "foo"\n  get / \n  ''', cursor_position=19)
    assert buffer_should_be_handled(mock_app)() is False
