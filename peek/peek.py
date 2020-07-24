"""Main module."""
import logging
import sys
from typing import List

from peek.commands import new_command, EsApiCall
from peek.config import get_config
from peek.errors import PeekError
from peek.key_bindings import key_bindings
from prompt_toolkit import PromptSession
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls
from pygments.lexers.javascript import JavascriptLexer
from pygments.styles.default import DefaultStyle

_logger = logging.getLogger(__name__)


class Repl:

    def __init__(self,
                 config_file: str = None,
                 extra_config_options: List[str] = None):
        self.state_new_command = True
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
                if self.state_new_command:
                    if text.strip() == '':
                        continue
                    try:
                        self.command = new_command(text)
                        self.state_new_command = False
                    except PeekError as e:
                        print(e)
                        continue
                else:
                    try:
                        self.command.run()
                    except Exception as e:
                        print(e)
                    finally:
                        self.state_new_command = True

        except EOFError:
            pass

    def signal_exit(self):
        self._should_exit = True

    def _get_message(self):
        return '> ' if self.state_new_command else '  '

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

