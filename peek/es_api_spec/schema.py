import ast
import json
import logging
import numbers
import os.path
import zipfile
from dataclasses import dataclass
from typing import List, Dict, Union, Any

from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document
from pygments.token import String, Name

from peek.es_api_spec.api_completer import can_match, ESApiCompleter
from peek.lexers import Slash, PathPart, Assign, CurlyLeft, CurlyRight, DictKey, Colon, EOF, BracketLeft
from peek.parser import ParserEventType

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

    def complete_payload(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        _logger.debug(f'Completing for API payload: {method!r} {path_tokens!r} {payload_tokens!r}')
        endpoint: Endpoint = self._get_matchable_endpoint(method, path_tokens)
        if endpoint is None or endpoint.request is None:
            return [], {}

        # TODO: refactor with parser state tracker
        payload_keys = []
        curly_level = 0
        for t in payload_tokens[:-1]:
            if t.ttype is CurlyLeft:
                curly_level += 1
            elif t.ttype is CurlyRight:
                curly_level -= 1
                payload_keys.pop()
            elif t.ttype is DictKey:
                if len(payload_keys) == curly_level - 1:
                    payload_keys.append(ast.literal_eval(t.value))
                elif len(payload_keys) == curly_level:
                    payload_keys[-1] = ast.literal_eval(t.value)
                else:
                    raise ValueError(f'Error when counting curly level {curly_level} and keys {payload_keys}')

        _logger.debug(f'Payload status: level: {curly_level}, keys: {payload_keys}')
        if curly_level == 0:  # not even in the first curly bracket, no completion
            return [], {}

        # Remove the payload key that is at the same level
        if curly_level == len(payload_keys):
            payload_keys.pop()

        body = Body.from_dict(self._schema.types[endpoint.request].body)
        name_to_values = body.candidate_keys(self._schema.types, payload_keys)

        return [Completion(c) for c in sorted(name_to_values.keys())], name_to_values

    def complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        _logger.debug(f'Completing for API payload value: {method!r} {path_tokens!r} {payload_tokens!r}')
        completions, context = self._do_complete_payload_value(document, complete_event, method, path_tokens,
                                                               payload_tokens, payload_events)
        return [Completion(c) for c in sorted(set(completions))], context

    def _do_complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        endpoint: Endpoint = self._get_matchable_endpoint(method, path_tokens)
        if endpoint.request is None:
            return [], {}

        unpaired_dict_key_tokens = []
        for payload_event in payload_events:
            if payload_event.type is ParserEventType.BEFORE_DICT_KEY_EXPR:
                _logger.debug(f'No completion is possible for payload with dict key expr: {payload_event.token}')
                return [], {}
            elif payload_event.type is ParserEventType.DICT_KEY:
                unpaired_dict_key_tokens.append(payload_event.token)
            elif payload_event.type is ParserEventType.AFTER_DICT_VALUE and payload_event.token.ttype is not EOF:
                unpaired_dict_key_tokens.pop()

        if not unpaired_dict_key_tokens:  # should not happen
            _logger.warning('No unpaired dict key tokens are found')
            return [], {}

        payload_keys = [ast.literal_eval(t.value) for t in unpaired_dict_key_tokens]
        _logger.debug(f'Payload keys are: {payload_keys}')

        # Find last Colon position
        for index_colon in range(len(payload_tokens) - 1, -1, -1):
            if payload_tokens[index_colon].ttype is Colon:
                break
        else:
            _logger.warning(f'Should not happen - Colon not found in payload: {payload_tokens}')
            return [], {}

        body = Body.from_dict(self._schema.types[endpoint.request].body)
        properties: List[Variable] = body.properties_for_keys(self._schema.types, payload_keys)
        if len(properties) == 0:
            return [], {}

        if index_colon == len(payload_tokens) - 1:  # Colon is the last token
            _logger.debug('Colon is the last token')
            # The simpler case when value position has nothing yet
            completions = []
            for prop in properties:
                completions += [json.dumps(v) for v in prop.candidate_values(self._schema.types)]
            return completions, {}
        else:
            token_after_colon = payload_tokens[index_colon + 1]
            last_payload_token = payload_tokens[-1]
            _logger.debug(f'The token after colon is: {token_after_colon}, last payload_token is: {last_payload_token}')
            if token_after_colon.ttype is BracketLeft:
                # if token_after_colon is last_payload_token or (last_payload_token.ttype is Comma):
                completions = []
                for prop in properties:
                    if isinstance(prop.value, ArrayOf):
                        # penetrate array
                        if last_payload_token.ttype in String:
                            completions += [v for v in
                                            prop.value.get_member().candidate_values(self._schema.types)
                                            if isinstance(v, str)]
                        else:
                            completions += [json.dumps(v) for v in
                                            prop.value.get_member().candidate_values(self._schema.types)]
                return completions, {}
            elif token_after_colon.ttype in String and token_after_colon is last_payload_token:
                completions = []
                for prop in properties:
                    completions += [v for v in prop.candidate_values(self._schema.types)
                                    if isinstance(v, str)]
                return completions, {}

            elif token_after_colon.ttype is Name and token_after_colon is last_payload_token:
                completions = []
                for prop in properties:
                    completions += [json.dumps(v) for v in prop.candidate_values(self._schema.types)
                                    if v in (True, False, None)]
                return completions, {}

        return [], {}  # catch all

    def _get_matchable_endpoint(self, method, path_tokens):
        try:
            token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
            endpoint = next(self._schema.matchable_endpoints(method, token_stream))
            _logger.debug(f'Found endpoint for {method!r} {path_tokens}')
            return endpoint
        except StopIteration:
            _logger.debug(f'No matching endpoint found for {method!r} {path_tokens}')
            return None


@dataclass(frozen=True)
class TypeDefinitionName:
    name: str
    namespace: str

    @staticmethod
    def from_dict(d):
        return TypeDefinitionName(d['name'], d['namespace'])


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


@dataclass(frozen=True)
class TypeDefinition:
    name: TypeDefinitionName
    data: Dict

    def candidate_values(self, types):
        return []

    def candidate_keys(self, types):
        return []

    def value_template(self, types):
        return []

    def __getattr__(self, item):
        return self.data.get(item, None)

    @staticmethod
    def from_dict(data):
        name = TypeDefinitionName.from_dict(data.pop('name'))
        kind = data.pop('kind')
        if kind == 'type_alias':
            return Alias(name=name, data=data)
        elif kind == 'interface':
            return Interface(name=name, data=data)
        elif kind == 'enum':
            return Enum(name=name, data=data)
        elif kind == 'request':
            return Request(name=name, data=data)
        elif kind == 'response':
            return Response(name=name, data=data)
        else:
            raise ValueError(f'unrecognized type definition kind [{kind}]')


@dataclass(frozen=True)
class Builtin(TypeDefinition):

    def candidate_values(self, types):
        if self.name.name == 'boolean':
            return [True, False]
        elif self.name.name == 'string':
            return ['']
        elif self.name.name == 'null':
            return [None]
        else:
            return []

    def value_template(self, types):
        if self.name.name == 'boolean':
            return [True]
        elif self.name.name == 'null':
            return [None]
        else:
            return []


@dataclass(frozen=True)
class Alias(TypeDefinition):

    def candidate_values(self, types):
        return self.get_type().candidate_values(types)

    def candidate_keys(self, types):
        return self.get_type().candidate_keys(types)

    def value_template(self, types):
        return self.get_type().value_template(types)

    def get_type(self):
        return Value.from_dict(self.type)


@dataclass(frozen=True)
class Interface(TypeDefinition):

    def candidate_values(self, types):
        return [{}]

    def candidate_keys(self, types):
        return self.get_properties()

    def value_template(self, types):
        return [{}]

    def get_properties(self):
        return [Variable.from_dict(prop) for prop in self.properties]


@dataclass(frozen=True)
class Enum(TypeDefinition):

    def candidate_values(self, types):
        return self.get_members()

    def value_template(self, types):
        return [self.get_members()[0]]

    def get_members(self) -> List[str]:
        return [member['name'] for member in self.members]


@dataclass(frozen=True)
class Request(TypeDefinition):

    def get_query(self):
        query = self.query
        if query is not None:
            if not isinstance(query, dict):
                query = {q['name']: q for q in self.query}
                self.data['query'] = query
        return query

    def get_attached_behaviours(self) -> List[str]:
        return self.attachedBehaviors


@dataclass(frozen=True)
class Response(TypeDefinition):
    pass


@dataclass(frozen=True)
class Value:
    data: Dict

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return []

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return []

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return []

    def __getattr__(self, item):
        return self.data.get(item, None)

    @staticmethod
    def from_dict(data):
        kind = data['kind']
        if kind == 'instance_of':
            return InstanceOf(data=data)
        elif kind == 'array_of':
            return ArrayOf(data=data)
        elif kind == 'dictionary_of':
            return DictionaryOf(data=data)
        elif kind == 'union_of':
            return UnionOf(data=data)
        elif kind == 'literal_value':
            return Literal(data=data)
        elif kind == 'user_defined_value':
            return UserDefined(data=data)
        elif kind == 'void_value':
            return Void(data=data)
        else:
            raise ValueError(f'unrecognized value kind [{kind}]')


@dataclass(frozen=True)
class InstanceOf(Value):

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return types[self.get_type_name()].candidate_values(types)

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return types[self.get_type_name()].candidate_keys(types)

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return types[self.get_type_name()].value_template(types)

    def get_type_name(self) -> TypeDefinitionName:
        return TypeDefinitionName.from_dict(self.type)


@dataclass(frozen=True)
class ArrayOf(Value):

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        member_value = self.get_member().candidate_values(types)
        if member_value == [{}]:
            return [[{}]]
        else:
            return [[]]

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        templates = [[]]
        templates += self.get_member().value_template(types)
        return templates

    def get_member(self) -> Value:
        return Value.from_dict(self.value)


@dataclass(frozen=True)
class DictionaryOf(Value):

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return [{}]

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        # TODO: check key type is string?
        return [Wildcard(self.value)]

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return [{}]

    def get_key(self) -> Value:
        return Value.from_dict(self.key)

    def get_value(self) -> Value:
        return Value.from_dict(self.value)

    def is_single_key(self) -> bool:
        return self.singleKey


@dataclass(frozen=True)
class UnionOf(Value):

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        all_results = []
        for member in self.get_members():
            all_results += member.candidate_values(types)
        return all_results

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        all_results = []
        for member in self.get_members():
            all_results += member.candidate_keys(types)
        return all_results

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        # TODO: this just return the first template
        return self.get_members()[0].value_template(types)

    def get_members(self):
        return [Value.from_dict(item) for item in self.items]


@dataclass(frozen=True)
class Literal(Value):

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return [self.get_value()]

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return [self.get_value()]

    def get_value(self):
        return self.value


@dataclass(frozen=True)
class UserDefined(Value):
    pass


@dataclass(frozen=True)
class Void(Value):
    pass


@dataclass(frozen=True)
class Wildcard(Value):

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return self.get_value().candidate_values(types)

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return self.get_value().candidate_keys(types)

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return self.get_value().value_template(types)

    def get_value(self):
        return Value.from_dict(self.data)


@dataclass(frozen=True)
class Variable:
    name: str
    aliases: List[str]
    value: Value

    def candidate_values(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return self.value.candidate_values(types)

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        return self.value.candidate_keys(types)

    def value_template(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]]):
        templates = self.value.value_template(types)
        if len(templates) == 0:
            _logger.warning(f'templates length is zero for [{self}]')
            return ''
        template = templates.pop()
        for t in templates[::-1]:
            # only list can take inner structure
            if isinstance(t, list):
                t.append(template)
            template = t

        return template

    @staticmethod
    def from_dict(data):
        return Variable(
            name=data['name'],
            aliases=data.get('aliases', []),
            value=Value.from_dict(data['type'])
        )


@dataclass(frozen=True)
class Body:
    data: Dict

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]],
                       payload_keys: List[str]):
        return {}

    def properties_for_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]],
                            payload_keys: List[str]) -> List:
        return []

    def __getattr__(self, item):
        return self.data.get(item, None)

    @staticmethod
    def from_dict(data):
        kind = data['kind']
        if kind == 'no_body':
            return NoBody(data)
        elif kind == 'value':
            return ValueBody(data)
        elif kind == 'properties':
            return PropertiesBody(data)
        else:
            raise ValueError(f'unrecognized body kind [{kind}]')


@dataclass(frozen=True)
class NoBody(Body):
    pass


@dataclass(frozen=True)
class ValueBody(Body):

    def get_value(self):
        return Value.of(self.value)


@dataclass(frozen=True)
class PropertiesBody(Body):

    def get_properties(self):
        return [Variable.from_dict(prop) for prop in self.properties]

    def candidate_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]],
                       payload_keys: List[str]) -> Dict[str, Any]:
        """
        For the given payload_keys, find properties that match the sequence, then return their sub-properties
        in the format of {property_name: property_template_value}.
        """

        if len(payload_keys) == 0:
            all_sub_properties = self.get_properties()
        else:
            matched_properties = self.properties_for_keys(types, payload_keys)
            all_sub_properties = []
            for prop in matched_properties:
                if not isinstance(prop, Wildcard) and isinstance(prop.value, ArrayOf):
                    # penetrate array
                    all_sub_properties += prop.value.get_member().candidate_keys(types)
                else:
                    all_sub_properties += prop.candidate_keys(types)

        name_to_value = {}
        for sub_prop in all_sub_properties:
            if not isinstance(sub_prop, Variable):
                continue
            name_to_value[sub_prop.name] = sub_prop.value_template(types)

        return name_to_value

    def properties_for_keys(self, types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]],
                            payload_keys: List[str]) -> List[Union[Variable, Wildcard]]:
        """
        For the given payload_keys, find properties that match the sequence. The result is a list of property
        because there could be more than one path that matches the key sequence.
        """
        candidate_properties = self.get_properties()
        if len(payload_keys) == 0:
            raise ValueError('no payload keys to find for properties')

        while len(payload_keys) > 0:
            matched_properties = []
            for prop in candidate_properties:
                if self._property_match_key(prop, payload_keys[0]):
                    matched_properties.append(prop)

            if len(matched_properties) == 0:  # No match is found
                return []

            # match is found
            payload_keys.pop(0)
            if len(payload_keys) == 0:
                return [p for p in matched_properties if isinstance(p, Variable) or isinstance(p, Wildcard)]

            # Prepare for the next round of key matching
            candidate_properties = []
            for matched_property in matched_properties:
                if not isinstance(matched_property, Wildcard) and isinstance(matched_property.value, ArrayOf):
                    # penetrate array
                    candidate_properties += matched_property.value.get_member().candidate_keys(types)
                else:
                    candidate_properties += matched_property.candidate_keys(types)

        return []  # should not reach here, but for safe

    @staticmethod
    def _property_match_key(prop, key):
        return prop.name == key or isinstance(prop, Wildcard) or (prop.aliases and key in prop.aliases)


class Schema:

    def __init__(self):
        data = self._load_bundled()
        self.endpoints = [Endpoint.from_dict(d) for d in data['endpoints']]
        self.types: Dict[TypeDefinitionName, Union[Alias, Interface, Enum, Request]] = {
            b.name: b for b in [
                Builtin(name=TypeDefinitionName("binary", "_builtins"), data={}),
                Builtin(name=TypeDefinitionName("boolean", "_builtins"), data={}),
                Builtin(name=TypeDefinitionName("null", "_builtins"), data={}),
                Builtin(name=TypeDefinitionName("number", "_builtins"), data={}),
                Builtin(name=TypeDefinitionName("string", "_builtins"), data={}),
                Builtin(name=TypeDefinitionName("void", "_builtins"), data={})
            ]
        }
        for d in data['types']:
            type_definition = TypeDefinition.from_dict(d)
            if isinstance(type_definition, Response):
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
        request: Request = self.types[endpoint.request]
        names = []
        if self._request_has_common_query_parameters(request):
            names += self._common_parameters.keys()

        query = request.get_query()
        if query is not None:
            names += query.keys()

        return names

    def query_param_values(self, param_name: str, endpoint: Endpoint):
        request: Request = self.types[endpoint.request]
        if self._request_has_common_query_parameters(request):
            if param_name in self._common_parameters.keys():
                return self._common_parameters[param_name]
        query_parameter = self._get_query_parameter(param_name, request)
        if query_parameter is None:
            return []
        return self._filter_for_param_values(query_parameter.candidate_values(self.types))

    def _build_common_params(self):
        type_definition = self.types[TypeDefinitionName('CommonQueryParameters', '_spec_utils')]
        if not isinstance(type_definition, Interface):
            _logger.warning(f'CommonQueryParameters type kind [{type_definition.kind}] unprocessable')
            return {}
        common_parameters = {}
        for prop in type_definition.properties:
            query_parameter = Variable.from_dict(prop)
            common_parameters[query_parameter.name] = self._filter_for_param_values(
                query_parameter.candidate_values(self.types))
        return common_parameters

    def _filter_for_param_values(self, candidate_values):
        final_values = []
        for value in candidate_values:
            if value is True:
                final_values.append('true')
            elif value is False:
                final_values.append('false')
            elif value is None:
                final_values.append('null')
            elif isinstance(value, (str, numbers.Number)):
                final_values.append(value)
        return final_values

    def _request_has_common_query_parameters(self, request: Request):
        attached_behaviours = request.get_attached_behaviours()
        return attached_behaviours is not None and 'CommonQueryParameters' in attached_behaviours

    def _get_query_parameter(self, param_name: str, request: TypeDefinition):
        query: Dict = request.get_query()
        if query is None:
            return None
        d = query.get(param_name, None)
        if d is None:
            return None
        return Variable.from_dict(d)

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
