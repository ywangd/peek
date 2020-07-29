"""Main module."""
import json
import logging
import sys
from json import JSONDecodeError
from typing import List

import pygments
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import PygmentsTokens, FormattedText
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls

from peek.completer import PeekCompleter
from peek.config import get_config, config_location
from peek.errors import PeekError, PeekSyntaxError
from peek.history import SqLiteHistory
from peek.key_bindings import key_bindings
from peek.lexers import PeekLexer, PeekStyle, PayloadLexer, Heading
from peek.parser import PeekParser
from peek.vm import PeekVM

_logger = logging.getLogger(__name__)

INPUT_HEADER = [(PeekStyle.styles[Heading], '>>>\n')]
OUTPUT_HEADER = FormattedText([(PeekStyle.styles[Heading], '===')])


class Peek:

    def __init__(self,
                 batch_mode=False,
                 config_file: str = None,
                 extra_config_options: List[str] = None):
        self._should_exit = False
        self.command = None
        self.config = get_config(config_file, extra_config_options)
        self._init_logging()
        self.batch_mode = batch_mode
        if self.batch_mode:
            self.session = None
        else:
            self.session = PromptSession(
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
        self.parser = PeekParser()
        self.vm = self._init_vm()

    def run(self):
        while True:
            try:
                text: str = self.session.prompt()
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
            except Exception as e:
                print(e)
                # if getattr(e, 'info'):
                #     print(e.info)

    def execute_stmt(self, stmt):
        if not self.batch_mode:
            print_formatted_text(OUTPUT_HEADER)
        response = self.vm.execute_stmt(stmt)
        try:
            if self.config.as_bool('pretty_print'):
                response = json.dumps(json.loads(response), indent=2)
            tokens = list(pygments.lex(response, lexer=PayloadLexer()))
            print_formatted_text(PygmentsTokens(tokens), style=style_from_pygments_cls(PeekStyle))
        except JSONDecodeError:
            print(response)

    def signal_exit(self):
        self._should_exit = True

    def _get_message(self):
        return INPUT_HEADER

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

    def _init_vm(self):
        auth = f'{self.config.get("username", "")}:{self.config.get("password", "")}'.strip()
        if auth == ':':
            auth = None

        return PeekVM(
            hosts=self.config.get('hosts', 'localhost:9200').split(','),
            auth=auth,
            use_ssl=self.config.as_bool('use_ssl'),
            verify_certs=self.config.as_bool('verify_certs'),
            ca_certs=self.config.get('ca_certs', None),
            client_cert=self.config.get('client_cert', None),
            client_key=self.config.get('client_key', None)
        )
