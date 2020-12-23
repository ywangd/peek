import ast
import json
import logging
from typing import List, Dict

from prompt_toolkit.completion import Completion, CompleteEvent
from prompt_toolkit.document import Document
from pygments.token import String, Name

from peek.common import PeekToken
from peek.es_api_spec.spec_js import build_js_specs
from peek.es_api_spec.spec_json import load_json_specs
from peek.lexers import Slash, PathPart, Assign, CurlyLeft, CurlyRight, DictKey, Colon, BracketLeft, EOF, Comma
from peek.parser import ParserEvent, ParserEventType

_logger = logging.getLogger(__name__)


class ApiSpec:

    def __init__(self, app, kibana_dir):
        self.app = app
        self.kibana_dir = kibana_dir
        self.specs = self._build_specs()

    def complete_url_path(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        cursor_token = path_tokens[-1]
        _logger.debug(f'Completing URL path: {cursor_token}')
        token_stream = [t.value for t in path_tokens if t.ttype is not Slash]
        if cursor_token.ttype is PathPart:
            token_stream.pop()
        candidates = []
        for api_name, api_spec in self.specs.items():
            if 'methods' not in api_spec:
                continue
            if method not in api_spec['methods']:
                continue
            for api_path in api_spec['patterns']:
                ps = [p for p in api_path.split('/') if p]
                # Nothing to complete if the candidate is shorter than current input
                if len(token_stream) >= len(ps):
                    continue
                if not can_match(token_stream, ps):
                    continue
                candidate = '/'.join(ps[len(token_stream):])
                candidates.append(Completion(candidate))
        return candidates

    def complete_query_param_name(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        _logger.debug(f'Completing URL query param name: {path_tokens[-1]}')
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_spec in matchable_specs(method, token_stream, self.specs):
            candidates.update(api_spec['url_params'].keys())
        return [Completion(c) for c in candidates]

    def complete_query_param_value(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        _logger.debug(f'Completing URL query param value: {path_tokens[-1]}')
        param_name_token = path_tokens[-2] if path_tokens[-1].ttype is Assign else path_tokens[-3]
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_spec in matchable_specs(method, token_stream, self.specs):
            v = api_spec['url_params'].get(param_name_token.value, None)
            if v is None:
                continue
            if v == '__flag__':
                candidates.update(('true', 'false'))
            elif isinstance(v, list) and len(v) > 0:
                candidates.update(v)
        return [Completion(c) for c in candidates]

    # TODO: refactor with parser state tracker
    def complete_payload(self, document: Document, complete_event: CompleteEvent, method, path_tokens, payload_tokens):
        _logger.debug(f'Completing for API payload: {method!r} {path_tokens!r} {payload_tokens!r}')
        rules = self._find_rules_for_method_and_url_path(method, path_tokens)
        if rules is None:
            return [], {}

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

        rules = self._resolve_rules_for_keys(rules, payload_keys)
        if rules is None:
            _logger.debug(f'Rules not available for key: {payload_keys!r}')
            return [], {}
        _logger.debug(f'Found rules for payload keys: {rules!r}')
        rules = dict(rules)  # avoid mutating original rules

        candidates = []
        for rule_key in list(rules.keys()):
            if rule_key == '__scope_link':
                _logger.debug(f'__scope_link not processed for rules: {rules}')
            elif rule_key == '__one_of':
                _logger.debug(f'__one_of not processed for rules: {rules}')
            elif rule_key == '*':
                _logger.debug(f'Wildcard * not processed for rules: {rules}')
            elif rule_key == '__template':
                __template = rules.get('__template', None)
                rules.pop('__template')
                if isinstance(__template, dict):
                    for k, v in __template.items():
                        if k not in rules:
                            rules[k] = v
                            candidates.append(Completion(k))
            else:
                candidates.append(Completion(rule_key))

        return candidates, rules

    def complete_payload_value(self, document: Document, complete_event: CompleteEvent, method: str,
                               path_tokens: List[PeekToken],
                               payload_tokens: List[PeekToken], payload_events: List[ParserEvent]):
        _logger.debug(f'Completing for API payload value: {method!r} {path_tokens!r} {payload_tokens!r}')
        rules = self._find_rules_for_method_and_url_path(method, path_tokens)
        if rules is None:
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

        rules = self._resolve_rules_for_keys(rules, payload_keys, unwrap_value_for_last_key=False)
        if rules is None:
            _logger.debug(f'Rules not available for keys: {payload_keys!r}')
            return [], {}
        _logger.debug(f'Found rules for payload keys: {rules!r}')

        # Find last Colon position
        for index_colon in range(len(payload_tokens) - 1, -1, -1):
            if payload_tokens[index_colon].ttype is Colon:
                break
        else:
            _logger.warning(f'Should not happen - Colon not found in payload: {payload_tokens}')
            return [], {}

        if index_colon == len(payload_tokens) - 1:  # Colon is the last token
            _logger.debug('Colon is the last token')
            # The simpler case when value position has nothing yet
            if isinstance(rules, dict):
                if '__one_of' in rules:
                    return [Completion('""' if isinstance(c, str) else json.dumps(c))
                            for c in rules['__one_of']], rules
                else:
                    return [Completion('{}')], rules
            elif isinstance(rules, list):
                if rules and isinstance(rules[0], dict):
                    return [Completion('[{}]')], rules
                else:
                    return [Completion('[]')], rules
            else:
                return [Completion(json.dumps(rules))], rules
        else:
            token_after_colon = payload_tokens[index_colon + 1]
            last_payload_token = payload_tokens[-1]
            _logger.debug(f'The token after colon is: {token_after_colon}, last payload_token is: {last_payload_token}')
            if token_after_colon.ttype is BracketLeft:
                if token_after_colon is last_payload_token or (last_payload_token.ttype is Comma):
                    if isinstance(rules, list) and rules and isinstance(rules[0], dict):
                        return [Completion('{}')], rules
            elif token_after_colon.ttype in String and token_after_colon is last_payload_token:
                if isinstance(rules, dict) and '__one_of' in rules:
                    return [Completion(c) for c in rules['__one_of'] if isinstance(c, str)], rules
                elif isinstance(rules, list):
                    return [Completion(c) for c in rules if isinstance(c, str)], rules
                elif isinstance(rules, str):
                    return [Completion(rules)], rules
            elif token_after_colon.ttype is Name and token_after_colon is last_payload_token:
                if isinstance(rules, dict) and '__one_of' in rules:
                    return [Completion(json.dumps(c)) for c in rules['__one_of'] if c in (True, False, None)], rules
                elif isinstance(rules, list):
                    return [Completion(json.dumps(c)) for c in rules if c in (True, False, None)], rules

        return [], {}  # catch all

    def _find_rules_for_method_and_url_path(self, method: str, path_tokens: List[PeekToken]):
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        try:
            api_spec = next(matchable_specs(method, token_stream, self.specs,
                                            required_field='data_autocomplete_rules'))
            _logger.debug(f'Found API spec for {method!r} {path_tokens}')
        except StopIteration:
            _logger.debug(f'No matching API spec found for {method!r} {path_tokens}')
            return None

        rules = self._maybe_process_rules([], api_spec.get('data_autocomplete_rules', None))
        _logger.debug('No rules found from spec' if rules is None else f'Found rules from spec: {rules}')
        return rules

    def _resolve_rules_for_keys(self, rules, payload_keys, unwrap_value_for_last_key=True):
        rules = self._do_resolve_rules_for_keys(rules, payload_keys,
                                                unwrap_value_for_last_key=unwrap_value_for_last_key)

        # If the first key lookup did not get anything, try with the GLOBAL space
        if rules is None and payload_keys[0] in self.specs['GLOBAL']:
            _logger.debug('Retry key with GLOBAL')
            rules = self._do_resolve_rules_for_keys(self.specs['GLOBAL'], payload_keys,
                                                    unwrap_value_for_last_key=unwrap_value_for_last_key)
        return rules

    def _do_resolve_rules_for_keys(self, rules, payload_keys, unwrap_value_for_last_key=True):
        history = [rules]
        for i, k in enumerate(payload_keys):
            if k not in rules and '*' in rules:
                _logger.debug(f'Matching * for key: {k!r}')
                rules = rules['*']
            elif k not in rules and '{field}' in rules:
                _logger.debug(f'Matching {{field}} for key: {k!r}')
                rules = rules['{field}']
            else:
                rules = rules.get(k, None)

            if not i == len(payload_keys) - 1 or unwrap_value_for_last_key:
                rules = self._maybe_process_rules(history, rules)
            else:
                rules = self._maybe_process_rules(history, rules, unwrap_value=False)
            if k == 'query' and rules == {}:
                _logger.debug('Special handling for empty "query" field')
                rules = self.specs['GLOBAL']['query']
            elif k == 'script' and (rules == {} or rules is None):
                _logger.debug(f'Special handling for script field: {rules!r}')
                rules = self.specs['GLOBAL']['script']

            _logger.debug(f'Rules for key {k!r} is: {rules}')
            history.append(rules)
            if rules is None:
                break
        return rules

    def _maybe_process_rules(self, history, rules, unwrap_value=True):
        if unwrap_value:
            processors = [
                self._maybe_resolve_scope_link,
                self._maybe_unwrap_for_dict,
                self._maybe_lift_one_of,
            ]
        else:
            processors = [
                self._maybe_resolve_scope_link,
                self._maybe_lift_one_of,
            ]
        while True:
            original_rules = rules
            for p in processors:
                rules = p(history, rules)
            if rules == original_rules:
                break
        return rules

    def _maybe_resolve_scope_link(self, history, rules):
        if isinstance(rules, dict) and '__scope_link' in rules:
            rules = dict(rules)  # avoid mutating original value
            _logger.debug(f'Found scope link: {rules!r}')
            scope_link = rules.pop('__scope_link')
            if scope_link.startswith('.'):
                _logger.debug(f'Found relative scope link: {scope_link}')
                if len(history) >= 2:
                    rules = history[-2]
                    if scope_link[1:] != '':
                        for scope_link_key in scope_link[1:].split('.'):
                            rules = rules[scope_link_key]
                else:
                    _logger.warning(f'History is not long enough to support relative scope link: {len(history)}')

            elif '.' in scope_link:
                scope = self.specs
                for scope_link_key in scope_link.split('.'):
                    if scope_link_key in scope:
                        scope = scope[scope_link_key]
                if id(scope) != id(self.specs):
                    rules.update(scope['data_autocomplete_rules'] if 'data_autocomplete_rules' in scope else scope)
            else:
                scope = self.specs.get(scope_link, None)
                if isinstance(scope, dict):
                    rules.update(scope['data_autocomplete_rules'] if 'data_autocomplete_rules' in scope else scope)
        return rules

    def _maybe_lift_one_of(self, history, rules):
        if isinstance(rules, dict) and '__one_of' in rules:
            rules = dict(rules)
            one_of = rules.pop('__one_of')
            if isinstance(one_of[0], dict):
                for e in one_of:
                    rules.update(e)
            else:
                rules['__one_of'] = one_of
        return rules

    def _maybe_unwrap_for_dict(self, history, rules):
        """
        If the rules is an list of dict, return the first dict
        """
        if isinstance(rules, dict):
            return rules
        elif isinstance(rules, list) and len(rules) > 0:
            if isinstance(rules[0], dict):
                return rules[0]
            else:
                return None
        else:
            return None

    def _build_specs(self):
        specs = {}
        if not self.app.batch_mode and self.app.config.as_bool('load_api_specs'):
            _logger.info(f'Build API specs from: {self.kibana_dir}')
            try:
                specs.update(load_json_specs(self.kibana_dir))
            except Exception:
                _logger.exception('Error loading JSON specs')
            specs = _merge_specs(specs, self._build_js_specs())
        return specs

    def _build_js_specs(self):
        specs = {}
        if self.app.config.as_bool('build_extended_api_specs'):
            _logger.info(f'Build extended API specs from: {self.kibana_dir}')
            try:
                specs = build_js_specs(self.kibana_dir, self.app.config.as_bool('cache_extended_api_specs'))
            except Exception:
                _logger.exception('Error building JS specs')
        return specs


def _merge_specs(basic_specs, extended_specs):
    specs = dict(basic_specs)
    for k, v in extended_specs.items():
        if k not in specs:
            specs[k] = v
        else:
            for kk, vv in v.items():
                if kk in specs[k]:
                    _logger.debug(f'Duplicated key found: {k}.{kk}')
                    if isinstance(specs[k][kk], dict) and isinstance(vv, dict):
                        specs[k][kk].update(vv)
                else:
                    specs[k][kk] = vv
    return specs


def matchable_specs(method: str, ts: List[str], specs: Dict, required_field='url_params') -> Dict:
    """
    Find the matchable spec for the given HTTP method and input path.
    """
    for api_name, api_spec in specs.items():
        if 'methods' not in api_spec:
            continue
        if method not in api_spec['methods']:
            continue
        if not api_spec.get(required_field, None):
            continue
        matched = False
        for pattern in api_spec['patterns']:
            ps = [p for p in pattern.split('/') if p]
            if len(ts) != len(ps):
                continue
            if not can_match(ts, ps):
                continue
            matched = True
            break
        if matched:
            yield api_spec


def can_match(ts, ps):
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
