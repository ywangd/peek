"""Main module."""
import json
import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Iterable

from prompt_toolkit import PromptSession, prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.processors import HighlightMatchingBracketProcessor
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls

from peek.capture import NoOpCapture, FileCapture
from peek.common import NONE_NS, AUTO_SAVE_NAME
from peek.completer import PeekCompleter
from peek.completions import monkey_patch_completion_state
from peek.config import get_config, config_location
from peek.connection import EsClientManager, connect, DelegatingListener
from peek.display import Display
from peek.errors import PeekError, PeekSyntaxError
from peek.history import SqLiteHistory
from peek.key_bindings import key_bindings
from peek.lexers import PeekLexer, PeekStyle, Heading, TipsMinor
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
        self.history = SqLiteHistory(self.config.as_int('history_max'))
        self.completer = PeekCompleter(self)
        self.display = Display(self)
        self.parser = PeekParser()
        self.vm = self._init_vm()
        self.prompt = self._init_prompt()
        monkey_patch_completion_state()
        # TODO: better name for signal payload json reformat
        self.is_pretty = True
        self._init_es_client_manager()
        self.ecm_backup_data = self.es_client_manager.to_dict()
        self._on_startup()

    def run(self):
        try:
            while not self._should_exit:
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
        finally:
            self.on_exit()

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

    def reset(self):
        self.completer.init_api_specs()
        self.vm = self._init_vm()
        self._repopulate_clients(EsClientManager.from_dict(self, self.ecm_backup_data))
        self._on_startup()

    def _get_message(self):
        idx = self.es_client_manager.index_current
        if idx is None:
            return FormattedText([
                (PeekStyle.styles[Heading], '>>>'),
                (PeekStyle.styles[TipsMinor], ' No Connection\n'),
            ])
        else:
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
                style=style_from_pygments_cls(PeekStyle),
                lexer=PygmentsLexer(PeekLexer),
                auto_suggest=AutoSuggestFromHistory(),
                completer=self.completer,
                history=self.history,
                multiline=True,
                key_bindings=key_bindings(self),
                enable_open_in_editor=True,
                enable_system_prompt=False,
                enable_suspend=True,
                search_ignore_case=True,
                clipboard=clipboard,
                mouse_support=Condition(self._should_support_mouse),
                swap_light_and_dark_colors=self.config.as_bool('swap_colour'),
                input_processors=[
                    HighlightMatchingBracketProcessor(chars="[](){}"),
                ],
            )

    def _init_es_client_manager(self):
        if self.cli_ns.zero_connection:
            self._repopulate_clients(EsClientManager())
            return

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

        if self._should_auto_load_session(options):
            _logger.info('Auto-loading connection state')
            data = self.history.load_session(AUTO_SAVE_NAME)
            if data is not None:
                self._repopulate_clients(EsClientManager.from_dict(self, json.loads(data)))
                return

        es_client_manager = EsClientManager()
        es_client_manager.add(connect(self, **options))
        self._repopulate_clients(es_client_manager)

    def _repopulate_clients(self, m: EsClientManager):
        """
        Detour to populate the clients due to dependency, e.g. on_add callback gets a reference of the App
        """
        self.es_client_manager = EsClientManager(listeners=[DelegatingListener(on_add=self._on_client_add)])
        for es_client in m.clients():
            self.es_client_manager.add(es_client)
        idx_current = m.index_current
        if idx_current is not None and idx_current < len(self.es_client_manager.clients()):
            self.es_client_manager.set_current(idx_current)

    def _init_vm(self):
        return PeekVM(self)

    def on_exit(self):
        if not self.batch_mode and self.config.as_bool('auto_save_session'):
            _logger.info('Auto-saving connection state')
            data = self.es_client_manager.to_dict()
            self.history.save_session(AUTO_SAVE_NAME, json.dumps(data))

    def _should_auto_load_session(self, options):
        """
        Auto load last auto-saved session only when:
        * configuration says so
        * running in interactive mode
        * No explicit connection parameters are specified (include those specified in connection section of rc file)
        """
        return (self.config.as_bool('auto_load_session') and
                not self.batch_mode and
                not options and
                self.config.get('connection') is None)

    def _should_support_mouse(self) -> bool:
        return self.config.as_bool('mouse_support')

    def _on_client_add(self, es_client_manager: EsClientManager):
        on_connection_add = self.config.get('on_connection_add')
        if on_connection_add is not None:
            self.process_input(on_connection_add)

    def _on_startup(self):
        on_startup = self.config.get('on_startup')
        if on_startup is not None:
            self.process_input(on_startup)
