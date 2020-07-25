"""Main module."""
import logging
import sys
from typing import List

from prompt_toolkit import PromptSession
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls
from pygments.lexers.javascript import JavascriptLexer
from pygments.styles.default import DefaultStyle

from peek.commands import new_command
from peek.config import get_config
from peek.errors import PeekError
from peek.key_bindings import key_bindings

_logger = logging.getLogger(__name__)


class Repl:

    def __init__(self,
                 config_file: str = None,
                 extra_config_options: List[str] = None):
        self._should_exit = False
        self.command = None
        self.config = get_config(config_file, extra_config_options)
        self._init_logging()
        self.session = PromptSession(
            message=self._get_message(),
            prompt_continuation='  ',
            style=style_from_pygments_cls(DefaultStyle),
            lexer=PygmentsLexer(JavascriptLexer),
            multiline=True,
            key_bindings=key_bindings(self),
            enable_open_in_editor=True,
            enable_system_prompt=True,
            enable_suspend=True,
            search_ignore_case=True
        )

    def run(self):
        try:
            while True:
                text = self.session.prompt()
                _logger.debug(f'input: {repr(text)}')
                if self._should_exit:
                    raise EOFError()
                if text.strip() == '':
                    continue
                try:
                    self.command = new_command(text)
                    self.command.run()
                except PeekError as e:
                    print(e)
                except Exception as e:
                    print(e)

        except EOFError:
            pass

    def signal_exit(self):
        self._should_exit = True

    def _get_message(self):
        return '> '

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

