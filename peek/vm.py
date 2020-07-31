import logging

from peek.errors import PeekError
from peek.parser import Stmt, FuncCallStmt, EsApiStmt
from peek.variables import VARIABLES, EsClient

_logger = logging.getLogger(__name__)


class PeekVM:

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.variables = {}
        self._load_variables(None)  # TODO
        # Load builtin variables last so they won't be overridden
        self.variables.update(VARIABLES)
        auth = f'{self.config.get("username", "")}:{self.config.get("password", "")}'.strip()
        self.es_client = EsClient(hosts=self.config.get('hosts', 'localhost:9200').split(','),
                                  auth=None if auth == ':' else auth,
                                  use_ssl=self.config.as_bool('use_ssl'),
                                  verify_certs=self.config.as_bool('verify_certs'),
                                  ca_certs=self.config.get('ca_certs', None),
                                  client_cert=self.config.get('client_cert', None),
                                  client_key=self.config.get('client_key', None))

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
            result = func(self, **stmt.options)
            return str(result) if result else None
        except Exception as e:
            return str(e)

    def execute_es_api_call(self, stmt: EsApiStmt):
        _logger.debug(f'Attempt to execute ES API call: {stmt}')
        try:
            return self.es_client.perform_request(stmt.method, stmt.path, stmt.payload)
        except Exception as e:
            if getattr(e, 'info'):
                return e.info
            return str(e)

    def set_es_client(self, es_client):
        self.es_client = es_client

    def _load_variables(self, path):
        """
        Load extra variables from given path
        """
        pass
