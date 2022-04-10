import functools
import itertools
import logging
import os
import re
from typing import Iterable
from unittest.mock import MagicMock

from configobj import ConfigObj

from peek.ast import NameNode, SymbolNode, DictNode, BinOpNode, TextNode, Node
from peek.config import config_location
from peek.parser import PeekParser
from peek.visitors import FormattingVisitor
from peek.visitors import Ref
from peek.vm import PeekVM, _BIN_OP_FUNCS

_CONST_SIMPLE_PATTERN = re.compile(r'^(export )?const (?P<name>\w+)[^=]* = (?P<rest>{[^;]*);?')
_CONST_COMPLEX_PATTERN = re.compile(r'^(export )?const (?P<name>\w+)[^=]* = '
                                    r'\(specService: SpecDefinitionsService\) => (?P<rest>{[^;]*);?')
_CONST_MULTI_PATTERN = re.compile(r'^(export )?const {(?P<names>[^}]*)} = (?P<value>.+);')
_RECORD_MEMBER_PATTERN = re.compile(r'(?P<assign>^\w+\.\w+ = {[^;]*);?')
_FUNCTION_PATTERN = re.compile(r'function \((?P<args>[^)]*)\) { *;?]')
_RETURN_PATTERN = re.compile(r'return (?P<value>.*)')

_logger = logging.getLogger(__name__)


# TODO: ingest.ts is parsed but processors seem to be ignored. Also don't know how it is referenced.

def build_js_specs(kibana_dir, use_cache_file):
    # Cache is not for efficiency, but rather because the spec building from TypeScript
    # files is hacky and likely to go wrong with new Kibana releases. Cache it so at least
    # we can have some usable version till a fix is ready for new releases.
    cached_extended_specs_file = os.path.expanduser(config_location()) + 'extended_specs.es'
    source = None
    if use_cache_file and os.path.exists(cached_extended_specs_file):
        _logger.info(f'Found cached extended specs file: {cached_extended_specs_file!r}')
        with open(cached_extended_specs_file) as ins:
            source = ins.read()
    spec_parser = JsSpecParser(kibana_dir, source=source)
    nodes = spec_parser.parse()
    spec_evaluator = JsSpecEvaluator()
    specs = spec_evaluator.visit(nodes)
    if use_cache_file and source is None:
        spec_parser.save(cached_extended_specs_file)
    _logger.info('Complete building extended specs')
    return specs


class JsSpecParser:

    def __init__(self, kibana_dir, source=None):
        self.kibana_dir = kibana_dir
        self.source = source
        self.nodes = []

    def parse(self):
        if self.source is None:
            self.source = self._extract_all()
        parser = PeekParser()
        self.nodes = parser.parse(self.source, log_level='WARNING')
        return self.nodes

    def save(self, output_file):
        content = []
        for node in self.nodes:
            content.append(FormattingVisitor(pretty=True).visit(node))
        with open(output_file, 'w') as outs:
            outs.write('\n'.join(content))

    def _extract_all(self):
        spec_file_contents = self.load_ts_specs(self.kibana_dir)
        sources = []
        # TODO: this file is imported by oss/query/dsl, we manually prioritize it but automation would be good
        dependency_file = '/oss/query/templates'
        if dependency_file in spec_file_contents:
            sources.extend(self._extract_from_one_file(dependency_file, spec_file_contents.pop(dependency_file)))
        for file_name, file_content in spec_file_contents.items():
            sources.extend(self._extract_from_one_file(file_name, file_content))
        text = '\n'.join(sources)
        return text.replace("rules['*']", "rules.'*'")

    def _extract_from_one_file(self, file_name, file_content):
        sources = [f'// {file_name}']
        state = ''
        for line in file_content.splitlines():
            stripped = line.strip()
            if '...[' in stripped:
                stripped = stripped.replace('...[', '_.splat % [')
            elif '...' in stripped:
                stripped = stripped.replace('...', '"...": @')
            if state == 'comments':
                if stripped.startswith('*/'):
                    state = ''
                else:
                    continue
            elif state == 'import':
                if stripped.endswith(';'):
                    state = ''
                continue
            elif stripped.startswith('/*'):
                if not stripped.endswith('*/'):
                    state = 'comments'
                continue
            elif stripped == '' or stripped.startswith('// '):
                continue
            elif stripped.startswith('import '):
                if stripped.endswith(';'):
                    continue
                elif stripped.endswith('{'):
                    assert state == '', f'import within other state: {state!r}'
                    state = 'import'
                    continue
                else:
                    raise ValueError(f'Unrecognised import variant: {stripped!r}')
            elif self._try_speical_0001(sources, stripped):
                continue
            elif self._try_special_0002(sources, stripped):
                continue
            elif self._try_const_simple_pattern(sources, stripped):
                continue
            elif self._try_const_complex_pattern(sources, stripped):
                continue
            elif self._try_const_multi_pattern(sources, stripped):
                continue
            elif self._try_record_member_assignment(sources, stripped):
                continue
            elif self._try_spec_service(sources, stripped):
                continue
            elif self._try_function(sources, stripped):
                continue
            elif self._try_return(sources, stripped):
                continue
            elif stripped.startswith('export '):
                continue
            elif stripped == 'gap_policy,':
                sources.append('"gap_policy": gap_policy,')
            elif stripped.endswith(';'):
                sources.append(stripped[:-1])
            else:
                sources.append(stripped)
        return sources

    def _try_const_simple_pattern(self, sources, stripped):
        m = _CONST_SIMPLE_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'let {m["name"]} = {m["rest"]}')
            return True
        else:
            return False

    def _try_const_complex_pattern(self, sources, stripped):
        m = _CONST_COMPLEX_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'for {m["name"]} in [0] {m["rest"]}')
            return True
        else:
            return False

    def _try_const_multi_pattern(self, sources, stripped):
        m = _CONST_MULTI_PATTERN.match(stripped)
        if m is not None:
            for name in m['names'].split(','):
                sources.append(f'let {name.strip()} = {m["value"]}')
            return True
        else:
            return False

    def _try_record_member_assignment(self, sources, stripped):
        m = _RECORD_MEMBER_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'let {m["assign"]}')
            return True
        else:
            return False

    def _try_spec_service(self, sources, stripped):
        if stripped.startswith('specService.'):
            sources.append(self._trim_semicolon(stripped.replace('specService.', 'specService ', 1)))
            return True
        else:
            return False

    def _try_function(self, sources, stripped):
        if stripped == 'function (s) {':
            sources.append('{')
            return True
        elif 'function (s) {' in stripped:
            sources.append(stripped.replace('function (s) {', '{'))
            return True
        else:
            return False

    def _try_return(self, sources, stripped):
        m = _RETURN_PATTERN.match(stripped)
        if m is not None:
            value = m["value"]
            if value.endswith(';'):
                value = value[:-1]
            sources.append(f'"return": """{value}"""')
            return True
        else:
            return False

    def _try_speical_0001(self, sources, stripped):
        if stripped == ''''*': { terms, histogram, date_histogram },''':
            sources.append('"*": { "terms": terms, "histogram": histogram, "date_histogram": date_histogram },')
            return True
        else:
            return False

    def _try_special_0002(self, sources, stripped):
        # TODO: filters.m is not handled
        if stripped == '''filters.m = filters.missing = {''':
            sources.append('let filters.missing = {')
            return True
        else:
            return False

    def load_ts_specs(self, kibana_dir):
        oss_path = os.path.join(
            kibana_dir, 'src', 'plugins', 'console', 'server', 'lib', 'spec_definitions', 'js')
        xpack_path = os.path.join(
            kibana_dir, 'x-pack', 'plugins', 'console_extensions', 'server', 'lib', 'spec_definitions', 'js')

        spec_file_contents = self._load_ts_specs(oss_path)
        spec_file_contents.update(self._load_ts_specs(xpack_path))
        return spec_file_contents

    def _load_ts_specs(self, base_dir):
        prefix = 'x-pack' if 'x-pack' in base_dir else 'oss'
        spec_file_contents = {}
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if not f.endswith('.ts'):
                    continue
                if f in ('shared.ts', 'index.ts'):  # TODO: skip
                    continue
                with open(os.path.join(root, f)) as ins:
                    file_key = os.path.join('/', prefix, root[len(base_dir) + 1:], f[:-3])
                    spec_file_contents[f'{file_key}'] = ins.read()

        return spec_file_contents

    def _trim_semicolon(self, line):
        return line[:-1] if line.endswith(';') else line


mock_app = MagicMock()
ConfigObj({
    'load_extension': False,
})
mock_app.display = MagicMock()
mock_app.parser = PeekParser()


class JsSpecEvaluator(PeekVM):

    def __init__(self):
        def flexible_dot(left_operand, right_operand):
            if isinstance(left_operand, list) and right_operand == 'sort':
                return lambda app: _sort(left_operand)
            elif isinstance(left_operand, list) and right_operand == 'flatMap':
                return lambda app, func: functools.partial(_flat_map, left_operand)(app, func)
            else:
                return _BIN_OP_FUNCS['.'](left_operand, right_operand)

        def flexible_mod(left_operand, right_operand):
            if left_operand == self.builtins['_']['splat']:
                return left_operand(right_operand)
            else:
                return _BIN_OP_FUNCS['%'](left_operand, right_operand)

        bin_op_funcs = dict(_BIN_OP_FUNCS)
        bin_op_funcs.update({
            '.': flexible_dot,
            '%': flexible_mod,
        })

        super().__init__(mock_app, bin_op_funcs=bin_op_funcs)
        mock_app.vm = self
        self.builtins = {
            '_': {
                'defaults': _defaults,
                'flatten': _flatten,
                'map': _map,
                'splat': self._splat,
            },
            'return': lambda _, v: v,
            'specService': lambda _, v: v,
            'addGlobalAutocompleteRules': add_global_autocomplete_rules,
            'addEndpointDescription': add_endpoint_description,
        }
        self.context = {
            'BOOLEAN': {
                "__one_of": [True, False]
            },
            'GLOBAL': {},
        }

    def visit(self, nodes):
        for node in nodes:
            self.execute_node(node)
        # Remove all loop iterator variables
        self.context = {k: v for k, v in self.context.items() if v != 0 and k != 's'}
        return self.context

    def visit_bin_op_node(self, node: BinOpNode):
        if node.op_token.value == '.' and isinstance(node.right_node, NameNode):
            node.right_node = TextNode(node.right_node.token)
        super(JsSpecEvaluator, self).visit_bin_op_node(node)

    def visit_dict_node(self, node: DictNode):
        d_ref = Ref()
        with self.consumer(lambda v: d_ref.set(v)):
            self._do_visit_dict_node(node, resolve_key_name=False)
        d = d_ref.get()
        if d.get('...', None) is not None:
            splat = d.pop('...')
            assert isinstance(splat, dict), f'Cannot splat type other than dict, got: {splat!r}'
            d.update(splat)
        self.consume(d)

    def visit_symbol_node(self, node: SymbolNode):
        self.consume(self.get_value(node.token.value))

    def visit_es_api_call_node(self, node):
        raise ValueError(f'SpecEvaluator cannot take ES API call node: {node!r}')

    def visit_shell_out_node(self, node):
        raise ValueError(f'SpecEvaluator cannot take shell out node: {node!r}')

    def _unwind_lhs(self, node: Node):
        if isinstance(node, BinOpNode):
            if node.op_token.value == '.' and isinstance(node.right_node, NameNode):
                node.right_node = TextNode(node.right_node.token)
        super(JsSpecEvaluator, self)._unwind_lhs(node)

    def _splat(self, values: Iterable):
        if not isinstance(values, Iterable):
            raise ValueError(f'Expect Iterable, got {values!r}')
        for v in values[:-1]:
            self.consume(v)
        return values[-1]


def add_global_autocomplete_rules(app, name, rule):
    app.vm.context['GLOBAL'][name] = rule


def add_endpoint_description(app, name, rule):
    app.vm.context[name] = rule


def _map(app, values, ret):
    ret_nodes = app.parser.parse('return ' + ret['return'], log_level='WARNING')
    results = []
    for value in values:
        app.vm.context['s'] = value
        v_ref = Ref()
        with app.vm.consumer(lambda v: v_ref.set(v)):
            ret_nodes[0].args_node.value_nodes[0].accept(app.vm)
        results.append(v_ref.get())
    return results


def _defaults(app, *args):
    d = {}
    for arg in args:
        d.update(arg)
    return d


def _flatten(app, *args):
    """
    This is specific to mappings.properties.format. NOT a generic flatten function
    """
    return list(itertools.chain(*args[0][0]))


def _flat_map(values, app, func):
    results = _map(app, values, func)
    return list(itertools.chain(*results))


def _sort(values):
    return sorted(values)
