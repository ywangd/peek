import logging
import os
import sys

from peek.errors import PeekError
from peek.parser import Stmt, FuncCallStmt, EsApiStmt
from peek.variables import VARIABLES

_logger = logging.getLogger(__name__)


class PeekVM:

    def __init__(self, app):
        self.app = app
        self.variables = {}
        self._load_variables()  # TODO
        # Load builtin variables last so they won't be overridden
        self.variables.update(VARIABLES)

    def execute_stmt(self, stmt: Stmt):
        return stmt.execute(self)

    def execute_func_call(self, stmt: FuncCallStmt):
        _logger.debug(f'Attempt to execute function call: {stmt}')
        func = self.variables.get(stmt.func_name)
        if func is None:
            raise PeekError(f'Unknown name: {stmt.func_name!r}')
        if not callable(func):
            raise PeekError(f'{stmt.func_name!r} is not a callable, but a {func!r}')
        try:
            result = func(self.app, **stmt.options)
            return str(result) if result else None
        except Exception as e:
            return str(e)

    def execute_es_api_call(self, stmt: EsApiStmt):
        _logger.debug(f'Attempt to execute ES API call: {stmt}')
        try:
            return self.app.es_client.perform_request(stmt.method, stmt.path, stmt.payload)
        except Exception as e:
            if getattr(e, 'info', None):
                return str(e.info)
            return str(e)

    def _load_variables(self):
        """
        Load extra variables from external paths
        """
        extension_path = self.app.config['extension_path']
        if not extension_path:
            return

        sys_path = sys.path[:]
        try:
            for p in extension_path.split(':'):
                if os.path.isfile(p):
                    self._load_one_extension(p)
                elif os.path.isdir(p):
                    for f in os.listdir(p):
                        if not f.endswith('.py'):
                            continue
                        self._load_one_extension(f)
        finally:
            sys.path = sys_path

    def _load_one_extension(self, p):
        import importlib
        fields = os.path.splitext(p)
        if len(fields) != 2 or fields[1] != '.py':
            _logger.warning(f'Extension must be python files, got: {p}')
            return
        sys.path.insert(0, os.path.dirname(fields[0]))
        try:
            m = importlib.import_module(os.path.basename(fields[0]))
            if isinstance(m.EXPORTS, dict):
                self.variables.update(m.EXPORTS)
                _logger.info(f'Loaded extension: {p!r}')
            else:
                _logger.warning(f'Ignore extension {p!r} since EXPORTS is not a dict, but: {m.EXPORTS!r}')
        except Exception as e:
            _logger.warning(f'Error on loading extension: {p!r}, {e}')
