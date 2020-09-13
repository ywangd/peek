import ast
import logging
from typing import List, Dict

from prompt_toolkit.completion import Completion, CompleteEvent
from prompt_toolkit.document import Document

from peek.es_api_spec.spec_js import build_js_specs
from peek.es_api_spec.spec_json import load_json_specs
from peek.lexers import Slash, PathPart, Assign, CurlyLeft, CurlyRight, DictKey

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
                candidates.append(Completion(candidate, start_position=0))
        return candidates

    def complete_query_param_name(self, document: Document, complete_event: CompleteEvent, method, path_tokens):
        _logger.debug(f'Completing URL query param name: {path_tokens[-1]}')
        token_stream = [t.value for t in path_tokens if t.ttype is PathPart]
        candidates = set()
        for api_spec in matchable_specs(method, token_stream, self.specs):
            candidates.update(api_spec['url_params'].keys())
        return [Completion(c, start_position=0) for c in candidates]

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
        return [Completion(c, start_position=0) for c in candidates]

    def complete_payload(self, document: Document, complete_event: CompleteEvent, method, path_tokens, payload_tokens):
        _logger.debug(f'Completing for API payload: {method!r} {path_tokens!r} {payload_tokens!r}')
        token_stream = [t.value for t in path_tokens if t.ttype is not Slash]

        try:
            api_spec = next(matchable_specs(method, token_stream, self.specs,
                                            required_field='data_autocomplete_rules'))
        except StopIteration:
            return []

        rules = self._maybe_process_rules(api_spec.get('data_autocomplete_rules', None))
        if rules is None:
            return []

        _logger.debug(f'Found rules from spec: {rules}')

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
            return []

        # Remove the payload key that is at the same level
        if curly_level == len(payload_keys):
            payload_keys.pop()

        rules = self._resolve_rules_for_keys(rules, payload_keys)
        if rules is None:
            _logger.debug(f'Rules not available for key: {payload_keys!r}')
            return []

        # TODO: __one_of, e.g. POST _render/template
        # TODO: top-level __template, e.g. POST _reindex
        # TODO: filters how does it work
        candidates = [Completion(k, start_position=0) for k in rules.keys()
                      if k not in ('__scope_link', '__template', '__one_of', '*')]
        return candidates, rules

    def _resolve_rules_for_keys(self, rules, payload_keys):
        for i, k in enumerate(payload_keys):
            if k not in rules and '*' in rules:
                rules = rules['*']
            else:
                rules = rules.get(k, None)
            rules = self._maybe_process_rules(rules)
            # Special handle for query
            if k == 'query' and rules == {}:
                rules = self.specs['GLOBAL']['query']
            if rules is None:
                break
        return rules

    def _maybe_process_rules(self, rules):
        processors = [
            self._maybe_resolve_scope_link,
            self._maybe_unwrap_for_dict,
            self._maybe_lift_one_of,
        ]
        while True:
            original_rules = rules
            for p in processors:
                rules = p(rules)
            if rules == original_rules:
                break
        return rules

    def _maybe_resolve_scope_link(self, rules):
        if isinstance(rules, dict) and '__scope_link' in rules:
            rules = dict(rules)  # avoid mutating original value
            _logger.debug(f'Found scope link: {rules!r}')
            scope_link = rules.pop('__scope_link')
            if scope_link.startswith('.'):  # TODO: relative scope link
                _logger.debug('Relative scope link not implemented')
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

    def _maybe_lift_one_of(self, rules):
        if isinstance(rules, dict) and '__one_of' in rules:
            rules = dict(rules)
            one_of = rules.pop('__one_of')
            if isinstance(one_of[0], dict):
                for e in one_of:
                    rules.update(e)
            else:
                rules['__one_of'] = one_of
        return rules

    def _maybe_unwrap_for_dict(self, rules):
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
