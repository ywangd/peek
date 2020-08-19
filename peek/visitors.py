import functools
import logging

from peek.ast import Visitor, EsApiCallNode, DictNode, KeyValueNode, ArrayNode, NumberNode, \
    StringNode, FuncCallNode, NameNode, TextNode, ShellOutNode, EsApiCallInlinePayloadNode, EsApiCallFilePayloadNode

_logger = logging.getLogger(__name__)


class Ref:

    def __init__(self, init_value=None):
        self._value = init_value

    def set(self, new_value):
        self._value = new_value

    def get(self):
        return self._value


class FormattingVisitor(Visitor):
    def __init__(self, pretty=False):
        super().__init__()
        self.pretty = pretty
        self.text = None
        self.indent_level = 0

    def visit(self, node):
        node.accept(self)
        return self.text

    def visit_es_api_call_node(self, node: EsApiCallNode):
        assert isinstance(node, EsApiCallNode)
        parts = [node.method_node.token.value, ' ', node.path_node.token.value]
        self.push_consumer(lambda v: parts.append(v))
        options_parts = []
        options_consumer = functools.partial(options_consumer_maker, options_parts)
        self._do_visit_dict_node(node.options_node, options_consumer)
        if options_parts:
            parts.append(' ' + ''.join(options_parts))
        parts.append('\n')

        if isinstance(node, EsApiCallInlinePayloadNode):
            for dict_node in node.dict_nodes:
                dict_node.accept(self)
                self.consume('\n')
        elif isinstance(node, EsApiCallFilePayloadNode):
            node.file_node.accept(self)
            self.consume('\n')
        else:
            raise ValueError(f'Unknown node: {node!r}')
        self.pop_consumer()
        self.text = ''.join(parts)

    def visit_func_call_node(self, node: FuncCallNode):
        assert isinstance(node, FuncCallNode)
        parts = [node.name_node.token.value, ' ']

        args_parts = []

        def func_args_consumer(v):
            if v == ',':
                args_parts.append(' ')
            elif v not in ['[', ']'] and v.strip() != '':
                args_parts.append(v)

        self._do_visit_array_node(node.args_node, func_args_consumer)
        if args_parts:
            parts += [''.join(args_parts), ' ']

        kwargs_parts = []
        func_kwargs_consumer = functools.partial(options_consumer_maker, kwargs_parts)
        self._do_visit_dict_node(node.kwargs_node, func_kwargs_consumer)
        if kwargs_parts:
            parts += [''.join(kwargs_parts)]
        self.text = ''.join(parts)

    def visit_shell_out_node(self, node: ShellOutNode):
        assert isinstance(node, ShellOutNode)
        self.text = f'!{node.command}'

    def visit_string_node(self, node: StringNode):
        self.consume(node.token.value)

    def visit_number_node(self, node: NumberNode):
        self.consume(node.token.value)

    def visit_name_node(self, node: NameNode):
        self.consume(node.token.value)

    def visit_text_node(self, node: TextNode):
        self.consume(node.token.value)

    def visit_key_value_node(self, node: KeyValueNode):
        node.key_node.accept(self)
        self.consume(':')
        if self.pretty:
            self.consume(' ')
        node.value_node.accept(self)

    def visit_dict_node(self, node: DictNode):
        parts = []
        self._do_visit_dict_node(node, lambda v: parts.append(v))
        self.consume(''.join(parts))

    def visit_array_node(self, node: ArrayNode):
        parts = []
        self._do_visit_array_node(node, lambda v: parts.append(v))
        self.consume(''.join(parts))

    def _do_visit_dict_node(self, node: DictNode, consumer):
        assert isinstance(node, DictNode)
        self.push_consumer(consumer)
        self.consume('{')
        if node.kv_nodes and self.pretty:
            self.consume('\n')
            self.indent_level += 1
        for i, kv_node in enumerate(node.kv_nodes):
            if self.indent_level >= 0:
                self.consume('  ' * self.indent_level)
            kv_node.accept(self)
            if i < len(node.kv_nodes) - 1:
                self.consume(',')
                if self.pretty:
                    self.consume('\n')
        if node.kv_nodes and self.pretty:
            self.consume('\n')
            self.indent_level -= 1
            if self.indent_level >= 0:
                self.consume('  ' * self.indent_level)
        self.consume('}')
        self.pop_consumer()

    def _do_visit_array_node(self, node: ArrayNode, consumer):
        assert isinstance(node, ArrayNode)
        self.push_consumer(consumer)
        self.consume('[')
        if node.value_nodes and self.pretty:
            self.consume('\n')
            self.indent_level += 1
        for i, value_node in enumerate(node.value_nodes):
            if self.indent_level >= 0:
                self.consume('  ' * self.indent_level)
            value_node.accept(self)
            if i < len(node.value_nodes) - 1:
                self.consume(',')
                if self.pretty:
                    self.consume('\n')
        if node.value_nodes and self.pretty:
            self.consume('\n')
            self.indent_level -= 1
            if self.indent_level >= 0:
                self.consume('  ' * self.indent_level)
        self.consume(']')
        self.pop_consumer()


def options_consumer_maker(options_parts, v):
    if v == ':':
        options_parts.append('=')
    elif v == ',':
        options_parts.append(' ')
    elif v not in ['{', '}'] and v.strip() != '':
        options_parts.append(v)
