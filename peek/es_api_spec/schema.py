import logging
import numbers
from dataclasses import dataclass
from typing import List, Dict, Union, Any

_logger = logging.getLogger(__name__)

Types = "Dict[TypeName, Union[Builtin, Alias, Interface, Enum, Request]]"


@dataclass(frozen=True)
class TypeName:
    name: str
    namespace: str

    @staticmethod
    def from_dict(data: Dict):
        return TypeName(data['name'], data['namespace'])


@dataclass(frozen=True)
class Endpoint:
    urls: List[Dict]
    request: TypeName
    description: str
    doc_url: str

    @staticmethod
    def from_dict(data: Dict):
        return Endpoint(
            urls=data['urls'],
            request=TypeName.from_dict(data['request']) if data['request'] else None,
            description=data['description'],
            doc_url=data['docUrl']
        )


@dataclass(frozen=True)
class TypeDefinition:
    name: TypeName
    data: Dict

    def candidate_values(self, types: Types):
        yield from []

    def candidate_properties(self, types: Types):
        return []

    def __getattr__(self, item):
        return self.data.get(item, None)

    @staticmethod
    def from_dict(data: Dict):
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

    def candidate_values(self, types: Types):
        if self.name.name == 'boolean':
            yield from [True, False]
        elif self.name.name == 'string':
            yield from ['']
        elif self.name.name == 'null':
            yield from [None]
        elif self.name.name == 'number':
            yield from [0]
        else:
            yield from []


@dataclass(frozen=True)
class Alias(TypeDefinition):

    def candidate_values(self, types: Types):
        yield from self.get_type().candidate_values(types)

    def candidate_properties(self, types: Types):
        return self.get_type().candidate_properties(types)

    def get_type(self):
        return Value.from_dict(self.type)


@dataclass(frozen=True)
class Interface(TypeDefinition):

    def candidate_values(self, types: Types):
        yield from [{}]

    def candidate_properties(self, types: Types):
        return [Variable.from_dict(prop) for prop in self.properties]


@dataclass(frozen=True)
class Enum(TypeDefinition):

    def candidate_values(self, types: Types):
        yield from self.get_members()

    def get_members(self) -> List[str]:
        return [member['name'] for member in self.members]


@dataclass(frozen=True)
class Request(TypeDefinition):

    def get_query(self) -> Dict:
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

    def candidate_values(self, types: Types):
        yield from []

    def candidate_properties(self, types: Types):
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

    def candidate_values(self, types: Types):
        type_name = self.get_type_name()
        if type_name in types:
            yield from types[type_name].candidate_values(types)
        else:
            _logger.debug(f'type [{type_name}] does not exist')
            yield from []

    def candidate_properties(self, types: Types):
        type_name = self.get_type_name()
        if type_name in types:
            return types[type_name].candidate_properties(types)
        else:
            _logger.debug(f'type [{type_name}] does not exist')
            yield from []

    def get_type_name(self) -> TypeName:
        return TypeName.from_dict(self.type)


@dataclass(frozen=True)
class ArrayOf(Value):

    def candidate_values(self, types: Types):
        member_value = next(self.get_member().candidate_values(types))
        if member_value == {}:
            yield from [[{}]]
        else:
            yield from [[]]

    def get_member(self) -> Value:
        return Value.from_dict(self.value)


@dataclass(frozen=True)
class DictionaryOf(Value):

    def candidate_values(self, types: Types):
        yield from [{}]

    def candidate_properties(self, types: Types):
        # TODO: check key type is string?
        return [Wildcard(self.get_value())]

    def get_key(self) -> Value:
        return Value.from_dict(self.key)

    def get_value(self) -> Value:
        return Value.from_dict(self.value)

    def is_single_key(self) -> bool:
        return self.singleKey


@dataclass(frozen=True)
class UnionOf(Value):

    def candidate_values(self, types: Types):
        for member in self.get_members():
            yield from member.candidate_values(types)

    def candidate_properties(self, types: Types):
        all_results = []
        for member in self.get_members():
            all_results.extend(member.candidate_properties(types))
        return all_results

    def get_members(self):
        return [Value.from_dict(item) for item in self.items]


@dataclass(frozen=True)
class Literal(Value):

    def candidate_values(self, types: Types):
        yield from [self.get_value()]

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

    def candidate_values(self, types: Types):
        yield from self.value.candidate_values(types)

    def candidate_properties(self, types: Types):
        return self.value.candidate_properties(types)

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

    def candidate_properties(self) -> List[Variable]:
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

    def candidate_properties(self) -> List[Variable]:
        return [Variable.from_dict(prop) for prop in self.properties]


class Schema:

    def __init__(self, data: Dict):
        self.endpoints = [Endpoint.from_dict(d) for d in data['endpoints']]
        self.types: Types = {
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

    def candidate_urls(self, method: str, ts: List[str]) -> List[str]:
        candidates = []
        for endpoint in self.endpoints:
            for url in endpoint.urls:
                if method not in url['methods']:
                    continue
                ps = [p for p in url['path'].split('/') if p]
                # Nothing to complete if the candidate is shorter than current input
                if len(ts) >= len(ps):
                    continue
                if not self._can_match(ts, ps):
                    continue
                candidate = '/'.join(ps[len(ts):])
                candidates.append(candidate)
        return sorted(candidates)

    def candidate_query_param_names(self, method: str, ts: List[str]) -> List[str]:
        candidates = set()
        for endpoint in self._matchable_endpoints(method, ts):
            request: Request = self.types[endpoint.request]
            if self._request_has_common_query_params(request):
                candidates.update(self._common_parameters.keys())
            query = request.get_query()
            if query is not None:
                candidates.update(query.keys())

        return sorted(candidates)

    def candidate_query_param_values(self, method: str, ts: List[str], param_name: str) -> List[str]:
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

    def candidate_sub_key_values(self, method, ts: List[str], payload_keys: List[str]) -> Dict[str, Any]:
        endpoint: Endpoint = self._matchable_endpoint(method, ts)
        if endpoint is None or endpoint.request is None:
            return {}
        sub_properties = self._sub_properties_for_keys(Body.from_dict(self.types[endpoint.request].body), payload_keys)
        key_to_values = {}
        for sub_prop in sub_properties:
            # Filter out wildcard to avoid showing '*' as a suggestion for dict keys
            if not isinstance(sub_prop, Variable) or isinstance(sub_prop, Wildcard):
                continue
            try:
                first_candidate_value = next(sub_prop.candidate_values(self.types))
            except StopIteration:
                # Some properties do not have candidate values, e.g. binary property
                # Just catch them all with an empty string
                first_candidate_value = ''

            key_to_values[sub_prop.name] = first_candidate_value
            for alias in sub_prop.aliases:
                key_to_values[alias] = first_candidate_value

        return key_to_values

    def candidate_values(self, method, ts: List[str], payload_keys: List[str], inside_array=False) -> List[Any]:
        endpoint: Endpoint = self._matchable_endpoint(method, ts)
        if endpoint is None or endpoint.request is None:
            return []
        properties = self._properties_for_keys(Body.from_dict(self.types[endpoint.request].body), payload_keys)
        values = []
        for prop in properties:
            if inside_array and isinstance(prop.value, ArrayOf):
                # penetrate array
                values.extend(prop.value.get_member().candidate_values(self.types))
            else:
                values.extend(prop.candidate_values(self.types))
        return values

    def _matchable_endpoints(self, method: str, ts: List[str]):
        for endpoint in self.endpoints:
            matched = False
            for url in endpoint.urls:
                if method not in url['methods']:
                    continue
                ps = [p for p in url['path'].split('/') if p]
                if len(ts) != len(ps):
                    continue
                if not self._can_match(ts, ps):
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

    def _properties_for_keys(self, body: Body, payload_keys: List[str]) -> List[Variable]:
        """
        For the given payload_keys, find properties that match the sequence. The result is a list of property
        because there could be more than one path that matches the key sequence.
        """
        if len(payload_keys) == 0:
            raise ValueError('no payload keys to find for properties')

        candidate_properties = body.candidate_properties()
        while len(payload_keys) > 0:
            matched_properties = []
            for candidate_property in candidate_properties:
                if not isinstance(candidate_property, Variable):
                    continue
                if candidate_property.match_key(payload_keys[0]):
                    matched_properties.append(candidate_property)

            if len(matched_properties) == 0:  # No match is found
                return []

            # match is found
            payload_keys.pop(0)
            if len(payload_keys) == 0:
                return [p for p in matched_properties if isinstance(p, Variable)]

            # Prepare for the next round of key matching
            candidate_properties = []
            for matched_property in matched_properties:
                candidate_properties.extend(self._sub_properties_for_property(self.types, matched_property))

        return []  # should not reach here, but for safe

    def _sub_properties_for_keys(self, body: Body,
                                 payload_keys: List[str]) -> List[Variable]:
        """
        For the given payload_keys, find properties that match the sequence, then return their sub-properties.
        """
        if len(payload_keys) == 0:
            return body.candidate_properties()
        else:
            matched_properties = self._properties_for_keys(body, payload_keys)
            sub_properties = []
            for matched_property in matched_properties:
                sub_properties.extend(self._sub_properties_for_property(self.types, matched_property))
            return sub_properties

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
    def _sub_properties_for_property(types: Types,
                                     matched_property: Variable):
        try:
            if isinstance(matched_property.value, ArrayOf):
                # penetrate array
                return matched_property.value.get_member().candidate_properties(types)
            else:
                return matched_property.candidate_properties(types)
        except KeyError as e:
            _logger.debug(f'error in _sub_properties_for_property: {e}')
            return []

    @staticmethod
    def _can_match(ts, ps):
        """
        Test whether the input path (ts) can match the candidate path (ps).
        The rule is basically a placeholder can match any string other than
        the ones leading with underscore.
        """
        for t, p in zip(ts, ps):
            if t != p:
                if t.startswith('_'):
                    return False
                if not (p.startswith('{') and p.endswith('}')):
                    return False
        return True

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
            elif isinstance(value, numbers.Number):
                final_values.append(str(value))
            elif isinstance(value, str):
                final_values.append(value)
            else:
                _logger.debug(f'non-usable query parameter value: {value!r}')
        return final_values

    @staticmethod
    def _request_has_common_query_params(request: Request) -> bool:
        attached_behaviours = request.get_attached_behaviours()
        return attached_behaviours is not None and 'CommonQueryParameters' in attached_behaviours

    @staticmethod
    def _get_query_parameter(param_name: str, request: Request) -> Union[Variable, None]:
        query: Dict = request.get_query()
        if query is None:
            return None
        d = query.get(param_name, None)
        if d is None:
            return None
        return Variable.from_dict(d)
