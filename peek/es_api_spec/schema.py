import json
import logging
import os.path
import zipfile
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document

from peek.es_api_spec.api_completer import can_match, ESApiCompleter
from peek.lexers import Slash, PathPart, Assign

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
            for url in endpoint.urls:
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
        _logger.debug(f'Completing URL query param name: {path_tokens[-1]}')
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for endpoint in self._schema.matchable_endpoints(method, token_stream):
            candidates.update(self._schema.query_param_names(endpoint))
        return [Completion(c) for c in candidates]

    def complete_query_param_value(self, document, complete_event, method, path_tokens):
        _logger.debug(f'Completing URL query param value: {path_tokens[-1]}')
        param_name_token = path_tokens[-2] if path_tokens[-1].ttype is Assign else path_tokens[-3]
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for endpoint in self._schema.matchable_endpoints(method, token_stream):
            candidates.update(self._schema.query_param_values(param_name_token.value, endpoint))
        return [Completion(c) for c in candidates]

    def complete_payload(self, document, complete_event, method, path_tokens, payload_tokens):
        return [], {}

    def complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        return [], {}


@dataclass(frozen=True)
class TypeDefinitionName:
    name: str
    namespace: str

    @staticmethod
    def from_dict(d):
        return TypeDefinitionName(d['name'], d['namespace'])


BOOLEAN_TYPE_NAME = TypeDefinitionName('boolean', '_builtins')


@dataclass(frozen=True)
class Endpoint:
    urls: List[Dict]
    request: TypeDefinitionName
    description: str
    doc_url: str

    @staticmethod
    def from_dict(d):
        return Endpoint(
            urls=d['urls'],
            request=TypeDefinitionName.from_dict(d['request']) if d['request'] else None,
            description=d['description'],
            doc_url=d['docUrl']
        )


class TypeDefinitionKind(Enum):
    ALIAS = 'type_alias'
    INTERFACE = 'interface'
    ENUM = 'enum'
    REQUEST = 'request'
    RESPONSE = 'response'


class VariableKind(Enum):
    INSTANCE_OF = "instance_of"
    ARRAY_OF = "array_of"
    DICTIONARY_OF = "dictionary_of"
    UNION_OF = "union_of"
    LITERAL_VALUE = "literal_value"
    USER_DEFINED_VALUE = "user_defined_value"
    VOID_VALUE = "void_value"


@dataclass(frozen=True)
class TypeDefinition:
    name: TypeDefinitionName
    kind: TypeDefinitionKind
    data: Dict

    def __getattr__(self, item):
        return self.data.get(item, None)

    @staticmethod
    def from_dict(d):
        name = TypeDefinitionName.from_dict(d.pop('name'))
        kind = TypeDefinitionKind(d.pop('kind'))
        # change query parameters to dict keyed by the parameter name
        if 'query' in d:
            d['query'] = {q['name']: q for q in d['query']}
        return TypeDefinition(
            name=name,
            kind=kind,
            data=d
        )


@dataclass(frozen=True)
class Variable:
    kind: VariableKind
    data: Dict

    def __getattr__(self, item):
        return self.data.get(item, None)

    @staticmethod
    def from_dict(data):
        return Variable(
            kind=VariableKind(data['kind']),
            data=data
        )


@dataclass(frozen=True)
class QueryParameter(Variable):
    name: str

    def candidate_values(self, types: Dict[TypeDefinitionName, TypeDefinition]):
        return self._resolve_variable(self, types)

    def _resolve_variable(self, variable: Variable, types: Dict[TypeDefinitionName, TypeDefinition]):
        if variable.kind == VariableKind.INSTANCE_OF:
            return self._resolve_type(TypeDefinitionName.from_dict(variable.type), types)
        elif variable.kind == VariableKind.ARRAY_OF:
            return self._resolve_variable(Variable.from_dict(variable.value), types)
        elif variable.kind == VariableKind.UNION_OF:
            all_results = []
            for item in variable.items:
                all_results += self._resolve_variable(Variable.from_dict(item), types)
            return all_results
        elif variable.kind == VariableKind.LITERAL_VALUE:
            return [variable.value]
        else:
            _logger.warning(f'query parameter variable kind [{variable.kind}] is not processable')
            return []

    def _resolve_type(self, type_name: TypeDefinitionName,
                      types: Dict[TypeDefinitionName, TypeDefinition]):
        if type_name == BOOLEAN_TYPE_NAME:
            return ['true', 'false']
        elif type_name.namespace == '_builtins':
            return []

        type_definition = types[type_name]
        if type_definition.kind == TypeDefinitionKind.ALIAS:
            return self._resolve_variable(Variable.from_dict(type_definition.type), types)
        elif type_definition.kind == TypeDefinitionKind.ENUM:
            return [member['name'] for member in type_definition.members]
        else:
            _logger.warning(f'query parameter type definition [{type_definition.kind}] is unprocessable')
            return []

    @staticmethod
    def from_dict(d):
        data = d['type']
        return QueryParameter(
            name=d['name'],
            kind=VariableKind(data['kind']),
            data=data
        )


class Schema:

    def __init__(self):
        data = self._load_bundled()
        self.endpoints = [Endpoint.from_dict(d) for d in data['endpoints']]
        self.types: Dict[TypeDefinitionName, TypeDefinition] = {}
        for d in data['types']:
            type_definition = TypeDefinition.from_dict(d)
            if type_definition.kind == TypeDefinitionKind.RESPONSE:
                continue
            self.types[type_definition.name] = type_definition
        self._common_parameters = self._build_common_params()

    def matchable_endpoints(self, method: str, ts: List[str]) -> List[Endpoint]:
        for endpoint in self.endpoints:
            matched = False
            for url in endpoint.urls:
                if method not in url['methods']:
                    continue
                ps = [p for p in url['path'].split('/') if p]
                if len(ts) != len(ps):
                    continue
                if not can_match(ts, ps):
                    continue
                matched = True
                break
            if matched:
                yield endpoint

    def query_param_names(self, endpoint: Endpoint):
        request_type = self.types[endpoint.request]
        names = []
        if self._request_has_common_query_parameters(request_type):
            names += self._common_parameters.keys()

        query = request_type.query
        if query is not None:
            names += query.keys()

        return names

    def query_param_values(self, param_name: str, endpoint: Endpoint):
        request_type = self.types[endpoint.request]
        if self._request_has_common_query_parameters(request_type):
            if param_name in self._common_parameters.keys():
                return self._common_parameters[param_name]
        query_parameter = self._get_query_parameter(param_name, request_type)
        if query_parameter is None:
            return []
        return query_parameter.candidate_values(self.types)

    def _request_has_common_query_parameters(self, request_type: TypeDefinition):
        attached_behaviours = request_type.attachedBehaviors
        return attached_behaviours is not None and 'CommonQueryParameters' in attached_behaviours

    def _build_common_params(self):
        type_definition = self.types[TypeDefinitionName('CommonQueryParameters', '_spec_utils')]
        if type_definition.kind != TypeDefinitionKind.INTERFACE:
            _logger.warning(f'CommonQueryParameters type kind [{type_definition.kind}] unprocessable')
            return {}
        common_parameters = {}
        for prop in type_definition.properties:
            query_parameter = QueryParameter.from_dict(prop)
            common_parameters[query_parameter.name] = query_parameter.candidate_values(self.types)
        return common_parameters

    def _get_query_parameter(self, param_name: str, request_type: TypeDefinition):
        query: Dict = request_type.query
        if query is None:
            return None
        d = query.get(param_name, None)
        if d is None:
            return None
        return QueryParameter.from_dict(d)

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
