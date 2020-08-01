import logging

from peek.errors import PeekError
from peek.parser import Stmt, FuncCallStmt, EsApiStmt
from peek.variables import VARIABLES

_logger = logging.getLogger(__name__)


class PeekVM:

    def __init__(self, app):
        self.app = app
        self.variables = {}
        self._load_variables(None)  # TODO
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

    def _load_variables(self, path):
        """
        Load extra variables from given path
        """
        pass

