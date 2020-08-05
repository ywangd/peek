"""Main module."""
import logging
import sys
from typing import List

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER

from peek.common import NONE_NS
from peek.completer import PeekCompleter
from peek.config import get_config, config_location
from peek.connection import AuthType, EsClientManger
from peek.display import Display
from peek.errors import PeekError, PeekSyntaxError
from peek.history import SqLiteHistory
from peek.key_bindings import key_bindings
from peek.lexers import PeekLexer, PeekStyle, Heading, TipsMinor
from peek.parser import PeekParser
from peek.names import func_connect
from peek.vm import PeekVM
from prompt_toolkit import PromptSession, print_formatted_text, prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls

_logger = logging.getLogger(__name__)

OUTPUT_HEADER = FormattedText([(PeekStyle.styles[Heading], '===')])


class PeekApp:

    def __init__(self,
                 batch_mode=False,
                 config_file: str = None,
                 extra_config_options: List[str] = None,
                 cli_ns=NONE_NS):
        self._should_exit = False
        self._preserved_text = ''
        self.batch_mode = batch_mode
        self.config = get_config(config_file, extra_config_options)
        self.cli_ns = cli_ns
        self._init_logging()
        self.es_client_manager = EsClientManger()
        self._init_es_client()
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
                _logger.debug(f'input: {repr(text)}')
                if self._should_exit:
                    raise EOFError()
                if text.strip() == '':
                    continue
                self.process_input(text)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    def process_input(self, text):
        """
        Process the input text, split it if it contains multiple commands.
        Note the multiple commands support here is separate from the syntax
        highlight. It maybe better if it can be merged somehow (TODO)
        """
        try:
            stmts = self.parser.parse(text)
        except PeekSyntaxError as e:
            print(e)
            return

        for stmt in stmts:
            try:
                self.execute_stmt(stmt)
            except PeekError as e:
                print(e)

    def execute_stmt(self, stmt):
        if not self.batch_mode:
            print_formatted_text(OUTPUT_HEADER)
            self.es_client
        response = self.vm.execute_stmt(stmt)
        self.display.show(response)

    def signal_exit(self):
        self._should_exit = True

    @property
    def preserved_text(self):
        return self._preserved_text

    @preserved_text.setter
    def preserved_text(self, value: str):
        self._preserved_text = value

    def add_es_client(self, es_client):
        self.es_client_manager.add(es_client)

    @property
    def es_client(self):
        return self.es_client_manager.current

    def request_input(self, message='', is_secret=False):
        return prompt(message=message, is_password=is_secret)

    def _get_message(self):
        return FormattedText([
            (PeekStyle.styles[Heading], '>>>'),
            (PeekStyle.styles[TipsMinor], f' [{self.es_client_manager._current}] {self.es_client}\n'),
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
            handler = logging.FileHandler(config_location() + log_file)

        log_level = getattr(logging, log_level, logging.WARNING)

        formatter = logging.Formatter(
            "%(asctime)s (%(process)d/%(threadName)s) "
            "%(name)s %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger(__package__)
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

    def _init_prompt(self):
        if self.batch_mode:
            return None
        else:
            return PromptSession(
                message=self._get_message(),
                style=style_from_pygments_cls(PeekStyle),
                lexer=PygmentsLexer(PeekLexer),
                auto_suggest=AutoSuggestFromHistory(),
                completer=PeekCompleter(),
                history=SqLiteHistory(),
                multiline=True,
                key_bindings=key_bindings(self),
                enable_open_in_editor=True,
                enable_system_prompt=True,
                enable_suspend=True,
                search_ignore_case=True,
            )

    def _init_es_client(self):
        func_connect(
            self,
            hosts=self.cli_ns.hosts,
            auth_type=AuthType.USERPASS if self.cli_ns.auth_type is None else AuthType(self.cli_ns.auth_type.upper()),
            username=self.cli_ns.username,
            password=self.cli_ns.password,
            api_key=self.cli_ns.api_key,
            use_ssl=self.cli_ns.use_ssl,
            verify_certs=self.cli_ns.verify_certs,
            ca_certs=self.cli_ns.ca_certs,
            client_cert=self.cli_ns.client_cert,
            client_key=self.cli_ns.client_key,
            force_prompt=self.cli_ns.force_prompt,
            no_prompt=self.cli_ns.no_prompt,
        )

    def _init_vm(self):
        return PeekVM(self)
