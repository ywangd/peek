import json
import logging
import os.path
import zipfile
from dataclasses import dataclass

from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document

from peek.es_api_spec.completer import can_match, ESApiCompleter
from peek.lexers import Slash, PathPart

_logger = logging.getLogger(__name__)


class ESSchemaCompleter(ESApiCompleter):

    def __init__(self):
        self._schema = Schema()

    def complete_url_path(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        cursor_token = path_tokens[-1]
        _logger.debug(f'Completing URL path: {cursor_token}')
        token_stream = [t.value for t in path_tokens if t.ttype is not Slash]
        if cursor_token.ttype is PathPart:
            token_stream.pop()
        candidates = []
        for endpoint in self._schema.endpoints:
            for url in endpoint['urls']:
                if method not in url['methods']:
                    continue
                ps = [p for p in url['path'].split('/') if p]
                # Nothing to complete if the candidate is shorter than current input
                if len(token_stream) >= len(ps):
                    continue
                if not can_match(token_stream, ps):
                    continue
                candidate = '/'.join(ps[len(token_stream):])
                candidates.append(Completion(candidate))

        return candidates

    def complete_query_param_name(self, document, complete_event, method, path_tokens):
        pass

    def complete_query_param_value(self, document, complete_event, method, path_tokens):
        pass

    def complete_payload(self, document, complete_event, method, path_tokens, payload_tokens):
        pass

    def complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        pass


@dataclass(frozen=True)
class QualifiedTypeName:
    name: str
    namespace: str

    @staticmethod
    def from_dict(d):
        return QualifiedTypeName(d['name'], d['namespace'])


class Schema:

    def __init__(self):
        data = self._load_bundled()
        self.endpoints = data['endpoints']
        self.types = {}
        for d in data['types']:
            self.types[QualifiedTypeName.from_dict(d)] = d

    @staticmethod
    def _load_bundled():
        f = os.path.join(os.path.dirname(__file__), 'schema.json.zip')
        return json.loads(zipfile.ZipFile(f).read('schema.json'))

    @staticmethod
    def _load_github(git_branch='main'):
        import urllib.request
        url = f'https://raw.githubusercontent.com/elastic/elasticsearch-specification/' \
              f'{git_branch}/output/schema/schema.json'
        return json.loads(urllib.request.urlopen(url).read())
