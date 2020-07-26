"""Main module."""
import json
import logging
import sys
from typing import List

import pygments
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import PygmentsTokens
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls
from pygments.lexers.javascript import JavascriptLexer

from peek.clients import EsClient
from peek.commands import new_command
from peek.completer import PeekCompleter
from peek.config import get_config
from peek.errors import PeekError
from peek.history import SqLiteHistory
from peek.key_bindings import key_bindings
from peek.lexers import PeekLexer, PeekStyle, PayloadLexer

_logger = logging.getLogger(__name__)


class Peek:

    def __init__(self,
                 config_file: str = None,
                 extra_config_options: List[str] = None):
        self._should_exit = False
        self.command = None
        self.config = get_config(config_file, extra_config_options)
        self._init_logging()
        self.session = PromptSession(
            message=self._get_message(),
            # prompt_continuation='  ',
            style=style_from_pygments_cls(PeekStyle),
            lexer=PygmentsLexer(PeekLexer),
            auto_suggest=AutoSuggestFromHistory(),
            completer=PeekCompleter(PeekLexer()),
            history=SqLiteHistory(),
            multiline=True,
            key_bindings=key_bindings(self),
            enable_open_in_editor=True,
            enable_system_prompt=True,
            enable_suspend=True,
            search_ignore_case=True,
        )
        self.es_client = self._init_es_client()

    def run(self):
        while True:
            try:
                text = self.session.prompt()
                _logger.debug(f'input: {repr(text)}')
                if self._should_exit:
                    raise EOFError()
                if text.strip() == '':
                    continue
                try:
                    self.command = new_command(text)
                    response = self.command.execute(self.es_client)
                    if self.config.as_bool('pretty_print'):
                        response = json.dumps(json.loads(response), indent=2)
                    tokens = list(pygments.lex(response, lexer=PayloadLexer()))
                    print('===')
                    print_formatted_text(PygmentsTokens(tokens), style=style_from_pygments_cls(PeekStyle))

                except PeekError as e:
                    print(e)
                except Exception as e:
                    print(e)
                    # if getattr(e, 'info'):
                    #     print(e.info)

            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    def signal_exit(self):
        self._should_exit = True

    def _get_message(self):
        return '>>>\n'

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
            handler = logging.FileHandler(log_file)

        log_level = getattr(logging, log_level, logging.WARNING)

        formatter = logging.Formatter(
            "%(asctime)s (%(process)d/%(threadName)s) "
            "%(name)s %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger(__package__)
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

    def _init_es_client(self):
        auth = f'{self.config.get("username", "")}:{self.config.get("password", "")}'.strip()
        if auth == ':':
            auth = None

        return EsClient(
            hosts=self.config.get('hosts', 'localhost:9200').split(','),
            auth=auth,
            use_ssl=self.config.as_bool('use_ssl'),
            verify_certs=self.config.as_bool('verify_certs'),
            ca_certs=self.config.get('ca_certs', None),
            client_cert=self.config.get('client_cert', None),
            client_key=self.config.get('client_key', None)
        )
