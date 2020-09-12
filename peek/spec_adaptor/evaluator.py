import itertools
from unittest.mock import MagicMock

from configobj import ConfigObj

from peek.ast import NameNode, SymbolNode, DictNode, BinOpNode, TextNode, Node
from peek.parser import PeekParser
from peek.visitors import Ref
from peek.vm import PeekVM

mock_app = MagicMock()
ConfigObj({
    'load_extension': False,
})
mock_app.display = MagicMock()
mock_app.parser = PeekParser()


class SpecEvaluator(PeekVM):

    def __init__(self):
        super().__init__(mock_app)
        mock_app.vm = self
        self.builtins = {
            '_': {
                'defaults': _defaults,
                'flatten': _flatten,
                'map': _map,
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
        super(SpecEvaluator, self).visit_bin_op_node(node)

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
        super(SpecEvaluator, self)._unwind_lhs(node)


def add_global_autocomplete_rules(app, name, rule):
    app.vm.context['GLOBAL'][name] = rule


def add_endpoint_description(app, name, rule):
    app.vm.context[name] = rule


def _map(app, values, ret):
    ret_nodes = app.parser.parse('return ' + ret['return'])
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
