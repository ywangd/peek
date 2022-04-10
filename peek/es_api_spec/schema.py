import json
import logging
import numbers
from dataclasses import dataclass
from typing import List, Dict, Union, Any

_logger = logging.getLogger(__name__)


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

    def __init__(self, data):
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
    def _load_github(git_branch='main'):
        import urllib.request
        url = f'https://raw.githubusercontent.com/elastic/elasticsearch-specification/' \
              f'{git_branch}/output/schema/schema.json'
        return json.loads(urllib.request.urlopen(url).read())
