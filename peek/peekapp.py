"""Main module."""
import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Iterable

from prompt_toolkit import PromptSession, prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.processors import HighlightMatchingBracketProcessor
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls

from peek.capture import NoOpCapture, FileCapture
from peek.common import NONE_NS
from peek.completer import PeekCompleter
from peek.config import get_config, config_location
from peek.connection import EsClientManager
from peek.display import Display
from peek.errors import PeekError, PeekSyntaxError
from peek.history import SqLiteHistory
from peek.key_bindings import key_bindings
from peek.lexers import PeekLexer, PeekStyle, Heading, TipsMinor
from peek.natives import ConnectFunc
from peek.parser import PeekParser
from peek.vm import PeekVM

_logger = logging.getLogger(__name__)


class PeekApp:

    def __init__(self,
                 batch_mode=False,
                 config_file: str = None,
                 extra_config_options: Iterable[str] = None,
                 cli_ns=NONE_NS):
        self._should_exit = False
        self._preserved_text = ''
        self.capture = NoOpCapture()
        self.batch_mode = batch_mode
        self.config = get_config(config_file, extra_config_options)
        self.cli_ns = cli_ns
        self._init_logging()
        self.es_client_manager = EsClientManager()
        self._init_es_client()
        self.history = SqLiteHistory(self.config.as_int('history_max'))
        self.prompt = self._init_prompt()
        self.display = Display(self)
        self.parser = PeekParser()
        self.vm = self._init_vm()

        # TODO: better name for signal payload json reformat
        self.is_pretty = True

    def run(self):
        while True:
            try:
                text: str = self.prompt.prompt(
                    message=self._get_message(),
                    default=self._get_default_text(),
                )
                _logger.debug(f'input: {text!r}')
                if self._should_exit:
                    raise EOFError()
                if text.strip() == '':
                    continue
                self.process_input(text)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    def process_input(self, text, echo=False):
        try:
            nodes = self.parser.parse(text)
        except PeekSyntaxError as e:
            self.display.error(e)
            return

        for node in nodes:
            try:
                if echo:
                    self.display.info(str(node))
                self.execute_node(node)
            except PeekError as e:
                self.display.error(e)
            except Exception as e:
                self.display.error(e)
                _logger.exception('Error on node execution')

    def execute_node(self, node):
        self.vm.execute_node(node)

    def signal_exit(self):
        self._should_exit = True

    def reset(self):
        self._init_es_client()
        for _ in range(len(self.es_client_manager.clients()) - 1):
            self.es_client_manager.remove_client(0)
        self.vm.context = {}

    def start_capture(self, f=None):
        if not isinstance(self.capture, NoOpCapture):
            raise PeekError(f'Cannot capture when one is currently running: {self.capture.status()}')

        if f is None:
            f = f'{datetime.now().strftime("%Y%m%d%H%M%S")}.es'
        self.capture = FileCapture(f)
        return self.capture.status()

    def stop_capture(self):
        if not isinstance(self.capture, NoOpCapture):
            self.capture.stop()
            self.capture = NoOpCapture()
            return 'Capture stopped'
        else:
            return 'No capture is running'

    @property
    def preserved_text(self):
        return self._preserved_text

    @preserved_text.setter
    def preserved_text(self, value: str):
        self._preserved_text = value

    def input(self, message='', is_secret=False):
        return prompt(message=message, is_password=is_secret)

    def _get_message(self):
        idx = self.es_client_manager.clients().index(self.es_client_manager.current)
        info_line = f' [{idx}] {self.es_client_manager.current}'
        if len(info_line) > 100:
            info_line = info_line[:97] + '...'
        return FormattedText([
            (PeekStyle.styles[Heading], '>>>'),
            (PeekStyle.styles[TipsMinor], info_line + '\n'),
        ])

    def _get_default_text(self):
        text = self.preserved_text
        if text:
            self.preserved_text = ''
        return text

    def _init_logging(self):
        log_file = self.config['log_file']
        log_level = self.config['log_level'].upper()
        if log_level == 'NONE':
            handler = logging.NullHandler()
        elif log_file == 'stderr':
            handler = logging.StreamHandler(sys.stderr)
        elif log_file == 'stdout':
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = logging.handlers.RotatingFileHandler(
                config_location() + log_file,
                maxBytes=10 * 1024 * 1024, backupCount=5)

        log_level = getattr(logging, log_level, logging.WARNING)

        formatter = logging.Formatter(
            '%(asctime)s (%(process)d/%(threadName)s) '
            '%(name)s %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger(__package__)
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

    def _init_prompt(self):
        if self.batch_mode:
            return None
        else:
            try:
                from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
                clipboard = PyperclipClipboard()
            except ImportError:
                clipboard = None

            return PromptSession(
                message=self._get_message(),
                style=style_from_pygments_cls(PeekStyle),
                lexer=PygmentsLexer(PeekLexer),
                auto_suggest=AutoSuggestFromHistory(),
                completer=PeekCompleter(self),
                history=self.history,
                multiline=True,
                key_bindings=key_bindings(self),
                enable_open_in_editor=True,
                enable_system_prompt=False,
                enable_suspend=True,
                search_ignore_case=True,
                clipboard=clipboard,
                mouse_support=False,
                swap_light_and_dark_colors=self.config.as_bool('swap_colour'),
                input_processors=[
                    HighlightMatchingBracketProcessor(chars="[](){}"),
                ],
            )

    def _init_es_client(self):
        options = {}
        keys = [
            'name',
            'hosts',
            'cloud_id',
            'username',
            'password',
            'api_key',
            'token',
            'use_ssl',
            'verify_certs',
            'assert_hostname',
            'ca_certs',
            'client_cert',
            'client_key',
            'force_prompt',
            'no_prompt',
        ]
        for k in keys:
            v = getattr(self.cli_ns, k, None)
            if v is not None:
                options[k] = v

        ConnectFunc()(self, **options)

    def _init_vm(self):
        return PeekVM(self)
