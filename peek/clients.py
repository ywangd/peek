import ast
import json
import logging
from typing import Optional

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


class PeekClient:

    def __init__(self, *args, **kwargs):
        self.lexer = PeekLexer()
        self.lexer.add_filter('tokenmerge')
        self.lexer.add_filter('raiseonerror', excclass=PeekSyntaxError)
        self.es_client = EsClient(*args, **kwargs)

    def execute_command(self, text):
        tokens = merge_unprocessed_tokens(self.lexer.get_tokens_unprocessed(text))
        if len(tokens) == 0:
            return
        if tokens[0][1] is Percent:
            return self.execute_special(tokens[1:])
        else:
            return self.execute_es_api_call(tokens)

    def execute_special(self, tokens):
        _logger.debug(f'attempt execute special command: {tokens}')
        command_token = tokens[0]
        if command_token[2] != 'conn':
            raise PeekError(f'Unknown special command: {repr(command_token[12])}')
        kwargs = {}
        for token in tokens[1:]:
            key, value = token[2].split('=', 1)
            try:
                kwargs[key] = ast.literal_eval(value)
            except Exception:
                kwargs[key] = value
        self.es_client = EsClient(**kwargs)
        return 'Success'

    def execute_es_api_call(self, tokens):
        _logger.debug('attempt execute ES API call')
        if len(tokens) < 2:
            raise InvalidEsApiCall(' '.join([t[2] for t in tokens]))
        method_token, path_token = tokens[0], tokens[1]
        if method_token[1] is not Keyword:
            raise InvalidHttpMethod(method_token[2])
        method = method_token[2].upper()
        path = path_token[2]
        path = path if path.startswith('/') else ('/' + path)
        _logger.debug(f'method: {repr(method)}, path: {repr(path)}')

        payload = construct_payload(tokens[2:])
        return self.es_client.perform_request(method, path, payload)


def construct_payload(tokens) -> Optional[str]:
    """
    Take merged unprocessed tokens for payload and construct a payload string
    """
    dict_level = 0
    payload = []
    for token in tokens:
        _logger.debug(f'dict_level: {dict_level}')
        idx, ttype, value = token
        if ttype is CurlyLeft:
            payload.append(value)
            dict_level += 1
        elif ttype is CurlyRight:
            payload.append(value)
            dict_level -= 1
            if dict_level == 0:
                payload.append('\n')  # support for ndjson
            elif dict_level < 0:
                raise PeekSyntaxError(f'Uneven curly: {token}')
        elif ttype in (BracketLeft, BracketRight, Comma, Colon):
            payload.append(value)
        elif ttype in Number:
            payload.append(value)
        elif ttype is Name.Builtin:  # true, false, null
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
            raise PeekSyntaxError(f'Unknown token: {token}')

    payload = ' '.join(payload) if payload else None
    _logger.debug(f'payload: {repr(payload)}')
    return payload


def merge_unprocessed_tokens(tokens):
    """
    Merge String tokens of the same types
    """
    merged_tokens = []
    current_token = None
    for token in tokens:
        if token[1] in (Whitespace, Comment.Single):
            if current_token is not None:
                merged_tokens.append(current_token)
                current_token = None
        elif token[1] in String:
            if current_token is not None and current_token[1] is token[1]:
                current_token = (current_token[0], current_token[1], current_token[2] + token[2])
            else:  # two consecutive strings with different quotes
                if current_token is not None:
                    merged_tokens.append(current_token)
                current_token = token
        else:
            if current_token is not None:
                merged_tokens.append(current_token)
                current_token = None
            merged_tokens.append(token)
    if current_token is not None:
        merged_tokens.append(current_token)

    _logger.debug(f'merged tokens: {merged_tokens}')
    return merged_tokens


class PeeKCommandInterpreter:

    def __init__(self):
        pass


class NoopDeserializer:
    def __init__(self):
        pass

    def loads(self, s, *args, **kwargs):
        return s


noopDeserializer = NoopDeserializer()
