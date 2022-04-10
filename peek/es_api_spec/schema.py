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
from peek.lexers import Slash, PathPart, Assign, CurlyLeft, CurlyRight, DictKey, Colon, EOF, BracketLeft, Comma
from peek.parser import ParserEventType

_logger = logging.getLogger(__name__)


class SchemaESApiCompleter(ESApiCompleter):

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
        return [Completion(c) for c in self._schema.query_param_names(method, token_stream)]

    def complete_query_param_value(self, document, complete_event, method, path_tokens):
        _logger.debug(f'Completing URL query param value: {path_tokens[-1]}')
        param_name_token = path_tokens[-2] if path_tokens[-1].ttype is Assign else path_tokens[-3]
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        return [Completion(c) for c in self._schema.query_param_values(method, token_stream, param_name_token.value)]

    def complete_payload(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        _logger.debug(f'Completing for API payload: {method!r} {path_tokens!r} {payload_tokens!r}')
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

        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        name_to_values = self._schema.candidate_keys(method, ts, payload_keys)
        return [Completion(c) for c in sorted(name_to_values.keys())], name_to_values

    def complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        _logger.debug(f'Completing for API payload value: {method!r} {path_tokens!r} {payload_tokens!r}')
        completions = self._do_complete_payload_value(document, complete_event, method, path_tokens,
                                                      payload_tokens, payload_events)
        return [Completion(c) for c in sorted(set(completions))], {}

    def _do_complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        unpaired_dict_key_tokens = []
        for payload_event in payload_events:
            if payload_event.type is ParserEventType.BEFORE_DICT_KEY_EXPR:
                _logger.debug(f'No completion is possible for payload with dict key expr: {payload_event.token}')
                return []
            elif payload_event.type is ParserEventType.DICT_KEY:
                unpaired_dict_key_tokens.append(payload_event.token)
            elif payload_event.type is ParserEventType.AFTER_DICT_VALUE and payload_event.token.ttype is not EOF:
                unpaired_dict_key_tokens.pop()

        if not unpaired_dict_key_tokens:  # should not happen
            _logger.warning('No unpaired dict key tokens are found')
            return []

        payload_keys = [ast.literal_eval(t.value) for t in unpaired_dict_key_tokens]
        _logger.debug(f'Payload keys are: {payload_keys}')

        # Find last Colon position
        for index_colon in range(len(payload_tokens) - 1, -1, -1):
            if payload_tokens[index_colon].ttype is Colon:
                break
        else:
            _logger.warning(f'Should not happen - Colon not found in payload: {payload_tokens}')
            return []

        ts = [t.value for t in path_tokens if t.ttype is PathPart]
        if index_colon == len(payload_tokens) - 1:  # Colon is the last token
            _logger.debug('Colon is the last token')
            # The simpler case when value position has nothing yet
            return [json.dumps(v) for v in self._schema.candidate_values(method, ts, payload_keys)]
        else:
            token_after_colon = payload_tokens[index_colon + 1]
            last_payload_token = payload_tokens[-1]
            _logger.debug(f'The token after colon is: {token_after_colon}, last payload_token is: {last_payload_token}')
            if token_after_colon.ttype is BracketLeft:
                if last_payload_token.ttype is BracketLeft or last_payload_token.ttype is Comma:
                    # no question asked, let's complete
                    values = self._schema.candidate_values(method, ts, payload_keys, inside_array=True)
                    return [json.dumps(v) for v in values]
                elif last_payload_token.ttype in String:
                    try:
                        ast.literal_eval(last_payload_token.value)
                    except SyntaxError:
                        # String is not complete, i.e. we are completing the string under cursor
                        values = self._schema.candidate_values(method, ts, payload_keys, inside_array=True)
                        return [v for v in values if isinstance(v, str)]

            elif token_after_colon.ttype in String and token_after_colon is last_payload_token:
                return [v for v in self._schema.candidate_values(method, ts, payload_keys) if isinstance(v, str)]
            elif token_after_colon.ttype is Name and token_after_colon is last_payload_token:
                return [json.dumps(v)
                        for v in self._schema.candidate_values(method, ts, payload_keys) if v in (True, False, None)]

        return []  # catch all


@dataclass(frozen=True)
class TypeName:
    name: str
    namespace: str

    @staticmethod
    def from_dict(d):
        return TypeName(d['name'], d['namespace'])


@dataclass(frozen=True)
class Endpoint:
    urls: List[Dict]
    request: TypeName
    description: str
    doc_url: str

    @staticmethod
    def from_dict(d):
        return Endpoint(
            urls=d['urls'],
            request=TypeName.from_dict(d['request']) if d['request'] else None,
            description=d['description'],
            doc_url=d['docUrl']
        )


@dataclass(frozen=True)
class TypeDefinition:
    name: TypeName
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
        name = TypeName.from_dict(data.pop('name'))
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

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return []

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return []

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
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

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return types[self.get_type_name()].candidate_values(types)

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return types[self.get_type_name()].candidate_keys(types)

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return types[self.get_type_name()].value_template(types)

    def get_type_name(self) -> TypeName:
        return TypeName.from_dict(self.type)


@dataclass(frozen=True)
class ArrayOf(Value):

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        member_value = self.get_member().candidate_values(types)
        if member_value == [{}]:
            return [[{}]]
        else:
            return [[]]

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        templates = [[]]
        templates += self.get_member().value_template(types)
        return templates

    def get_member(self) -> Value:
        return Value.from_dict(self.value)


@dataclass(frozen=True)
class DictionaryOf(Value):

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return [{}]

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        # TODO: check key type is string?
        return [Wildcard(self.get_value())]

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return [{}]

    def get_key(self) -> Value:
        return Value.from_dict(self.key)

    def get_value(self) -> Value:
        return Value.from_dict(self.value)

    def is_single_key(self) -> bool:
        return self.singleKey


@dataclass(frozen=True)
class UnionOf(Value):

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        all_results = []
        for member in self.get_members():
            all_results += member.candidate_values(types)
        return all_results

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        all_results = []
        for member in self.get_members():
            all_results += member.candidate_keys(types)
        return all_results

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        # TODO: this just return the first template
        return self.get_members()[0].value_template(types)

    def get_members(self):
        return [Value.from_dict(item) for item in self.items]


@dataclass(frozen=True)
class Literal(Value):

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return [self.get_value()]

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
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
class Variable:
    name: str
    aliases: List[str]
    value: Value

    def candidate_values(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return self.value.candidate_values(types)

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
        return self.value.candidate_keys(types)

    def value_template(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]]):
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

    def match_key(self, key: str):
        return self.name == key or key in self.aliases

    @staticmethod
    def from_dict(data):
        return Variable(
            name=data['name'],
            aliases=data.get('aliases', []),
            value=Value.from_dict(data['type'])
        )


@dataclass(frozen=True, init=False)
class Wildcard(Variable):

    def __init__(self, value: Value):
        super(Wildcard, self).__init__(name='*', aliases=[], value=value)

    def match_key(self, key: str):
        return True


@dataclass(frozen=True)
class Body:
    data: Dict

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]],
                       payload_keys: List[str]):
        return {}

    def properties_for_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]],
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

    def candidate_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]],
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
                if isinstance(prop.value, ArrayOf):
                    # penetrate array
                    all_sub_properties += prop.value.get_member().candidate_keys(types)
                else:
                    all_sub_properties += prop.candidate_keys(types)

        name_to_value = {}
        for sub_prop in all_sub_properties:
            # Filter out wildcard to avoid showing '*' as a suggestion for dict keys
            if not isinstance(sub_prop, Variable) or isinstance(sub_prop, Wildcard):
                continue
            value_template = sub_prop.value_template(types)
            name_to_value[sub_prop.name] = value_template
            for alias in sub_prop.aliases:
                name_to_value[alias] = value_template

        return name_to_value

    def properties_for_keys(self, types: Dict[TypeName, Union[Alias, Interface, Enum, Request]],
                            payload_keys: List[str]) -> List[Variable]:
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
                if not isinstance(prop, Variable):
                    continue
                if prop.match_key(payload_keys[0]):
                    matched_properties.append(prop)

            if len(matched_properties) == 0:  # No match is found
                return []

            # match is found
            payload_keys.pop(0)
            if len(payload_keys) == 0:
                return [p for p in matched_properties if isinstance(p, Variable)]

            # Prepare for the next round of key matching
            candidate_properties = []
            for matched_property in matched_properties:
                if isinstance(matched_property.value, ArrayOf):
                    # penetrate array
                    candidate_properties += matched_property.value.get_member().candidate_keys(types)
                else:
                    candidate_properties += matched_property.candidate_keys(types)

        return []  # should not reach here, but for safe


class Schema:

    def __init__(self):
        data = self._load_bundled()
        self.endpoints = [Endpoint.from_dict(d) for d in data['endpoints']]
        self.types: Dict[TypeName, Union[Alias, Interface, Enum, Request]] = {
            b.name: b for b in [
                Builtin(name=TypeName("binary", "_builtins"), data={}),
                Builtin(name=TypeName("boolean", "_builtins"), data={}),
                Builtin(name=TypeName("null", "_builtins"), data={}),
                Builtin(name=TypeName("number", "_builtins"), data={}),
                Builtin(name=TypeName("string", "_builtins"), data={}),
                Builtin(name=TypeName("void", "_builtins"), data={})
            ]
        }
        for d in data['types']:
            type_definition = TypeDefinition.from_dict(d)
            if isinstance(type_definition, Response):
                continue
            self.types[type_definition.name] = type_definition
        self._common_parameters = self._build_common_params()

    def query_param_names(self, method: str, ts: List[str]) -> List[str]:
        candidates = set()
        for endpoint in self._matchable_endpoints(method, ts):
            request: Request = self.types[endpoint.request]
            if self._request_has_common_query_params(request):
                candidates.update(self._common_parameters.keys())
            query = request.get_query()
            if query is not None:
                candidates.update(query.keys())

        return sorted(candidates)

    def query_param_values(self, method: str, ts: List[str], param_name: str) -> List[str]:
        candidates = set()
        for endpoint in self._matchable_endpoints(method, ts):
            request: Request = self.types[endpoint.request]
            if self._request_has_common_query_params(request) and param_name in self._common_parameters.keys():
                candidates.update(self._common_parameters[param_name])
            else:
                query_param = self._get_query_parameter(param_name, request)
                if query_param is not None:
                    candidates.update(self._filter_for_param_values(query_param.candidate_values(self.types)))

        return sorted(candidates)

    def candidate_keys(self, method, ts: List[str], payload_keys: List[str]) -> Dict[str, Any]:
        endpoint: Endpoint = self._matchable_endpoint(method, ts)
        if endpoint.request is None:
            return {}
        body = Body.from_dict(self.types[endpoint.request].body)
        return body.candidate_keys(self.types, payload_keys)

    def candidate_values(self, method, ts: List[str], payload_keys: List[str], inside_array=False) -> List[Any]:
        endpoint: Endpoint = self._matchable_endpoint(method, ts)
        if endpoint.request is None:
            return []
        body = Body.from_dict(self.types[endpoint.request].body)
        properties = body.properties_for_keys(self.types, payload_keys)
        values = []
        for prop in properties:
            if inside_array and isinstance(prop.value, ArrayOf):
                values += prop.value.get_member().candidate_values(self.types)
            else:
                values += prop.candidate_values(self.types)
        return values

    def _matchable_endpoints(self, method: str, ts: List[str]) -> List[Endpoint]:
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

    def _matchable_endpoint(self, method, ts: List[str]) -> Union[Endpoint, None]:
        try:
            endpoint = next(self._matchable_endpoints(method, ts))
            _logger.debug(f'Found endpoint for {method!r} {ts}')
            return endpoint
        except StopIteration:
            _logger.debug(f'No matching endpoint found for {method!r} {ts}')
            return None

    def _build_common_params(self) -> Dict[str, List[str]]:
        type_definition = self.types[TypeName('CommonQueryParameters', '_spec_utils')]
        if not isinstance(type_definition, Interface):
            _logger.warning(f'CommonQueryParameters type kind [{type_definition.kind}] unprocessable')
            return {}
        common_parameters = {}
        for prop in type_definition.properties:
            query_parameter = Variable.from_dict(prop)
            common_parameters[query_parameter.name] = self._filter_for_param_values(
                query_parameter.candidate_values(self.types))
        return common_parameters

    @staticmethod
    def _filter_for_param_values(candidate_values) -> List[str]:
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

    @staticmethod
    def _request_has_common_query_params(request: Request) -> bool:
        attached_behaviours = request.get_attached_behaviours()
        return attached_behaviours is not None and 'CommonQueryParameters' in attached_behaviours

    @staticmethod
    def _get_query_parameter(param_name: str, request: TypeDefinition) -> Union[Variable, None]:
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
