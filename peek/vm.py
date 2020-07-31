import logging

from elasticsearch import Elasticsearch

from peek.errors import PeekError
from peek.parser import Stmt, FuncCallStmt, EsApiStmt

_logger = logging.getLogger(__name__)


class EsClient:

    def __init__(self,
                 hosts='localhost:9200',
                 auth=None,
                 use_ssl=False, verify_certs=False, ca_certs=None,
                 client_cert=None, client_key=None):
        self.es = Elasticsearch(
            hosts=hosts,
            http_auth=auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            ca_certs=ca_certs,
            client_cert=client_cert,
            client_key=client_key,
            ssl_show_warn=False,
        )

    def perform_request(self, method, path, payload):
        deserializer = self.es.transport.deserializer
        try:
            # Avoid deserializing the response since we parse it with the main loop for syntax highlighting
            self.es.transport.deserializer = noopDeserializer
            return self.es.transport.perform_request(method, path, body=payload)
        finally:
            self.es.transport.deserializer = deserializer


class PeekVM:

    def __init__(self, *args, **kwargs):
        self.es_client = EsClient(*args, **kwargs)

    def execute_stmt(self, stmt: Stmt):
        return stmt.execute(self)

    def execute_func_call(self, stmt: FuncCallStmt):
        _logger.debug(f'Attempt to execute function call: {stmt}')
        if stmt.func_name != 'conn':
            raise PeekError(f'Unknown function: {stmt.func_name!r}')
        self.es_client = EsClient(**stmt.options)
        return 'Success'

    def execute_es_api_call(self, stmt: EsApiStmt):
        _logger.debug(f'Attempt to execute ES API call: {stmt}')
        return self.es_client.perform_request(stmt.method, stmt.path, stmt.payload)


class NoopDeserializer:
    def __init__(self):
        pass

    def loads(self, s, *args, **kwargs):
        return s


noopDeserializer = NoopDeserializer()
