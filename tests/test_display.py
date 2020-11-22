from io import StringIO
from unittest.mock import MagicMock, patch

from prompt_toolkit.formatted_text import PygmentsTokens, FormattedText

from peek.display import Display
from peek.natives import EXPORTS

mock_app = MagicMock(name='PeekApp')
mock_app.batch_mode = False
mock_app.vm.functions = {k: v for k, v in EXPORTS.items() if callable(v)}
capture_outs = StringIO()

config = {'swap_colour': False, 'pretty_print': True}
mock_app.config.as_bool = MagicMock(side_effect=lambda x: config.get(x))
mock_app.config.__getitem__ = MagicMock(side_effect=lambda x: config.get(x))

display = Display(mock_app)

print_formatted_text = MagicMock()


def test_display_will_not_show_None():
    print_formatted_text = MagicMock()
    with patch('peek.display.print_formatted_text', print_formatted_text):
        mock_app.batch_mode = False
        mock_app.capture.file = MagicMock(return_value=None)
        display.info(None)
        print_formatted_text.assert_not_called()

        mock_app.capture.file = MagicMock(return_value=None)
        display.error(None)
        print_formatted_text.assert_not_called()


def test_display_will_tokenize():
    print_formatted_text = MagicMock()
    with patch('peek.display.print_formatted_text', print_formatted_text):
        mock_app.batch_mode = False
        mock_app.capture.file = MagicMock(return_value=None)

        display.info('"foo"')
        print_formatted_text.assert_called_with(
            _PygmentsToken(),
            style=display.style,
            style_transformation=display.style_transformation)

        display.info('"foo" 42 "bar"')
        print_formatted_text.assert_called_with(
            _PygmentsToken(),
            style=display.style,
            style_transformation=display.style_transformation)

        display.info({"foo": "bar"})
        print_formatted_text.assert_called_with(
            _PygmentsToken(),
            style=display.style,
            style_transformation=display.style_transformation)


def test_display_will_print_plain_when_tokenize_is_impossible():
    print_formatted_text = MagicMock()
    with patch('peek.display.print_formatted_text', print_formatted_text):
        mock_app.batch_mode = False
        capture_outs.truncate()
        mock_app.capture.file = MagicMock(return_value=capture_outs)
        display.info('[0]  http://localhost:9200')
        print_formatted_text.assert_called_with(
            '[0]  http://localhost:9200',
            style=display.style,
            style_transformation=display.style_transformation)

        capture_outs.seek(0)
        assert capture_outs.read() == '=== \n[0]  http://localhost:9200\n'


def test_display_will_error():
    print_formatted_text = MagicMock()
    with patch('peek.display.print_formatted_text', print_formatted_text):
        mock_app.batch_mode = False
        mock_app.capture.file = MagicMock(return_value=None)
        error = RuntimeError('This is an error')
        display.error(error)
        print_formatted_text.assert_called_with(
            error,
            style=display.style,
            style_transformation=display.style_transformation)


def test_display_will_not_print_header_when_in_batch_mode():
    print_formatted_text = MagicMock()
    with patch('peek.display.print_formatted_text', print_formatted_text):
        mock_print = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.isatty = MagicMock(return_value=False)
        with patch('builtins.print', mock_print), patch('sys.stdout', mock_stdout):
            mock_app.capture.file = MagicMock(return_value=None)
            mock_app.batch_mode = True
            display.info(1)
            print_formatted_text.assert_not_called()
            mock_print.assert_called_once_with('1', file=mock_stdout, end='')


def test_display_will_support_formatted_text():
    print_formatted_text = MagicMock()
    with patch('peek.display.print_formatted_text', print_formatted_text):
        mock_app.batch_mode = False
        mock_app.capture.file = MagicMock(return_value=None)
        source_message = FormattedText()
        display.info(source_message)
        print_formatted_text.assert_called_with(
            source_message, style=display.style, style_transformation=display.style_transformation)
        source_error = FormattedText()
        display.error(source_error)
        print_formatted_text.assert_called_with(
            source_error, style=display.style, style_transformation=display.style_transformation)


class _PygmentsToken:

    def __eq__(self, other):
        return type(other) is PygmentsTokens

    def __next__(self, other):
        return type(other) is not PygmentsTokens

    def __repr__(self):
        return '_PygmentsToken'
