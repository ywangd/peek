import ast
import json
import logging

from elasticsearch import Elasticsearch
from pygments.token import Whitespace, Comment, Keyword, Number, Name, String

from peek.errors import PeekSyntaxError, InvalidHttpMethod, InvalidEsApiCall, PeekError
from peek.lexers import PeekLexer, Percent, CurlyLeft, CurlyRight, BracketLeft, BracketRight, Comma, Colon

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
            client_key=client_key
        )

    def perform_request(self, method, path, payload):
        deserializer = self.es.transport.deserializer
        try:
            # Avoid deserializing the response since we parse it with the main loop for syntax highlighting
            self.es.transport.deserializer = noopDeserializer
            return self.es.transport.perform_request(method, path, body=payload)
        finally:
            self.es.transport.deserializer = deserializer


class PeekClient:

    def __init__(self, *args, **kwargs):
        self.lexer = PeekLexer()
        self.lexer.add_filter('tokenmerge')
        self.lexer.add_filter('raiseonerror', excclass=PeekSyntaxError)
        self.es_client = EsClient(*args, **kwargs)

    def execute_command(self, text):
        tokens = [t for t in self.lexer.get_tokens(text) if t[0] not in (Whitespace, Comment.Single)]
        if len(tokens) == 0:
            return
        if tokens[0][0] is Percent:
            return self.execute_special(tokens[1:])
        else:
            return self.execute_es_api_call(tokens)

    def execute_special(self, tokens):
        _logger.debug(f'attempt execute special command: {tokens}')
        command_token = tokens[0]
        if command_token[1] != 'conn':
            raise PeekError(f'Unknown special command: {repr(command_token[1])}')
        kwargs = {}
        for token in tokens[1:]:
            key, value = token[1].split('=', 1)
            try:
                kwargs[key] = ast.literal_eval(value)
            except Exception:
                kwargs[key] = value
        self.es_client = EsClient(**kwargs)
        return 'Success'

    def execute_es_api_call(self, tokens):
        _logger.debug('attempt execute ES API call')
        if len(tokens) < 2:
            raise InvalidEsApiCall(' '.join([t[1] for t in tokens]))
        method_token, path_token = tokens[0], tokens[1]
        if method_token[0] is not Keyword:
            raise InvalidHttpMethod(method_token[1])
        method = method_token[1].upper()
        path = path_token[1]
        path = path if path.startswith('/') else ('/' + path)

        dict_level = 0
        payload = []
        for (ttype, value) in tokens[2:]:
            if ttype is CurlyLeft:
                payload.append(value)
                dict_level += 1
            elif ttype is CurlyRight:
                payload.append(value)
                dict_level -= 1
                if dict_level == 0:
                    payload.append('\n')
                elif dict_level < 0:
                    raise PeekSyntaxError("Uneven curly bracket")
            elif ttype in (BracketLeft, BracketRight, Comma, Colon):
                payload.append(value)
            elif ttype in Number:
                payload.append(value)
            elif ttype is Name.Builtin:
                payload.append(value.lower())
            elif ttype is String.Symbol:
                if value.startswith("'"):
                    payload.append(json.dumps(ast.literal_eval(value)))
                else:
                    payload.append(value)
            elif ttype is String.Double:
                payload.append(value)
            elif ttype is String.Single:
                payload.append(json.dumps(ast.literal_eval(value)))
            else:
                raise PeekSyntaxError((ttype, value))

        payload = ' '.join(payload) if payload else None
        _logger.debug(f'method: {repr(method)}, path: {repr(path)}, payload: {repr(payload)}')
        return self.es_client.perform_request(method, path, payload)


class PeeKCommandInterpreter:

    def __init__(self):
        pass

class NoopDeserializer:
    def __init__(self):
        pass

    def loads(self, s, *args, **kwargs):
        return s


noopDeserializer = NoopDeserializer()
