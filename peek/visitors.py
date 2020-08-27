import functools
import logging

from peek.ast import Visitor, EsApiCallNode, DictNode, KeyValueNode, ArrayNode, NumberNode, \
    StringNode, FuncCallNode, NameNode, TextNode, ShellOutNode, EsApiCallInlinePayloadNode, EsApiCallFilePayloadNode, \
    BinOpNode, UnaryOpNode, GroupNode, SymbolNode, LetNode, ForInNode

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
        self.parts = []
        self.indent_level = 0

    def visit(self, node):
        self.parts = []
        self.indent_level = 0
        with self.consumer(lambda *args: self.parts.extend(args)):
            node.accept(self)
        return ''.join(self.parts)

    def visit_es_api_call_node(self, node: EsApiCallNode):
        self.consume(node.method_node.token.value, ' ')
        if isinstance(node.path_node, TextNode):
            self.consume(node.path_node.token.value)
        else:
            node.path_node.accept(self)
        options_parts = []
        options_consumer = functools.partial(options_consumer_maker, options_parts)
        self._do_visit_dict_node(node.options_node, options_consumer)
        if options_parts:
            self.consume(' ' + ''.join(options_parts))
        self.consume('\n')
        self.consume(self._indent())

        if isinstance(node, EsApiCallInlinePayloadNode):
            for dict_node in node.dict_nodes:
                dict_node.accept(self)
                self.consume('\n')
        elif isinstance(node, EsApiCallFilePayloadNode):
            node.file_node.accept(self)
            self.consume('\n')
        else:
            raise ValueError(f'Unknown node: {node!r}')

    def visit_func_call_node(self, node: FuncCallNode):
        node.name_node.accept(self)
        if node.is_stmt:
            self.consume(' ')
        else:
            self.consume('(')

        arg_separator = self._arg_separator(node)

        symbols_parts = []

        def func_symbols_consumer(*args):
            for v in args:
                if v == ',':
                    symbols_parts.append(arg_separator)
                elif v not in ['[', ']'] and v.strip() != '':
                    symbols_parts.append(f'{v}')

        self._do_visit_array_node(node.symbols_node, func_symbols_consumer)
        if symbols_parts:
            self.consume(''.join(symbols_parts))

        args_parts = []

        def func_args_consumer(*args):
            for v in args:
                if v == ',':
                    args_parts.append(arg_separator)
                elif v not in ['[', ']'] and v.strip() != '':
                    args_parts.append(v)

        self._do_visit_array_node(node.args_node, func_args_consumer)

        if args_parts:
            if symbols_parts:
                self.consume(arg_separator)
            self.consume(''.join(args_parts))

        kwargs_parts = []
        func_kwargs_consumer = functools.partial(options_consumer_maker, kwargs_parts)
        self._do_visit_dict_node(node.kwargs_node, func_kwargs_consumer)
        if kwargs_parts:
            kwargs_parts = [x if x != ' ' else arg_separator for x in kwargs_parts]
            if args_parts or args_parts:
                self.consume(arg_separator)
            self.consume(''.join(kwargs_parts))
        if not node.is_stmt:
            self.consume(')')

    def visit_let_node(self, node: LetNode):
        self.consume('let', ' ')
        assignments_parts = []
        assignments_consumer = functools.partial(options_consumer_maker, assignments_parts)
        self._do_visit_dict_node(node.assignments_node, assignments_consumer)
        if assignments_parts:
            self.consume(''.join(assignments_parts))

    def visit_shell_out_node(self, node: ShellOutNode):
        self.consume(f'!{node.command}')

    def visit_for_in_node(self, node: ForInNode):
        self.consume('for', ' ')
        node.item.accept(self)
        self.consume(' ', 'in', ' ')
        node.items.accept(self)
        self.consume(' ', '{', '\n')
        self.indent_level += 1
        for n in node.suite:
            self.consume(self._indent())
            n.accept(self)
            self.consume('\n')
        self.indent_level -= 1
        self.consume(self._indent(), '}')

    def visit_string_node(self, node: StringNode):
        self.consume(node.token.value)

    def visit_number_node(self, node: NumberNode):
        self.consume(node.token.value)

    def visit_name_node(self, node: NameNode):
        self.consume(node.token.value)

    def visit_symbol_node(self, node: SymbolNode):
        self.consume('@', node.token.value)

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

    def visit_bin_op_node(self, node: BinOpNode):
        node.left_node.accept(self)
        self.consume(node.op_token.value)
        node.right_node.accept(self)

    def visit_unary_op_node(self, node: UnaryOpNode):
        self.consume(node.op_token.value)
        node.operand_node.accept(self)

    def visit_group_node(self, node: GroupNode):
        self.consume('(')
        node.grouped.accept(self)
        self.consume(')')

    def _do_visit_dict_node(self, node: DictNode, consumer):
        self.push_consumer(consumer)
        self.consume('{')
        if node.kv_nodes and self.pretty:
            self.consume('\n')
            self.indent_level += 1
        for i, kv_node in enumerate(node.kv_nodes):
            if self.pretty:
                self.consume(self._indent())
            kv_node.accept(self)
            if i < len(node.kv_nodes) - 1:
                self.consume(',')
                if self.pretty:
                    self.consume('\n')
        if node.kv_nodes and self.pretty:
            self.consume('\n')
            self.indent_level -= 1
            self.consume(self._indent())
        self.consume('}')
        self.pop_consumer()

    def _do_visit_array_node(self, node: ArrayNode, consumer):
        self.push_consumer(consumer)
        self.consume('[')
        if node.value_nodes and self.pretty:
            self.consume('\n')
            self.indent_level += 1
        for i, value_node in enumerate(node.value_nodes):
            self.consume(self._indent())
            value_node.accept(self)
            if i < len(node.value_nodes) - 1:
                self.consume(',')
                if self.pretty:
                    self.consume('\n')
        if node.value_nodes and self.pretty:
            self.consume('\n')
            self.indent_level -= 1
            self.consume(self._indent())
        self.consume(']')
        self.pop_consumer()

    def _indent(self):
        return '  ' * self.indent_level

    def _arg_separator(self, node: FuncCallNode):
        if node.is_stmt:
            return ' '
        else:
            if self.pretty:
                return ', '
            else:
                return ','


class TreeFormattingVisitor(Visitor):

    def __init__(self, indent_chars='  '):
        super().__init__()
        self.indent_chars = indent_chars
        self.lines = []
        self.indent_level = 0
        self.lines = []

    def visit(self, node):
        self.lines = []
        self.push_consumer(lambda v: self.lines.append(v))
        node.accept(self)
        self.pop_consumer()
        return '\n'.join(self.lines)

    def visit_es_api_call_node(self, node: EsApiCallNode):
        self.consume(f'{self._indent()}EsApiStmt')
        self.indent_level += 1
        node.method_node.accept(self)
        node.path_node.accept(self)
        node.options_node.accept(self)
        if isinstance(node, EsApiCallInlinePayloadNode):
            for n in node.dict_nodes:
                n.accept(self)
        elif isinstance(node, EsApiCallFilePayloadNode):
            node.file_node.accept(self)
        else:
            raise ValueError(f'Unknown node: {node!r}')
        self.indent_level -= 1

    def visit_func_call_node(self, node: FuncCallNode):
        self.consume(f'{self._indent()}Func{"Stmt" if node.is_stmt else "Expr"}({node.name_node!r})')
        self.indent_level += 1
        node.symbols_node.accept(self)
        node.args_node.accept(self)
        node.kwargs_node.accept(self)
        self.indent_level -= 1

    def visit_let_node(self, node: LetNode):
        self.consume(f'{self._indent()}LetStmt')
        self.indent_level += 1
        node.assignments_node.accept(self)
        self.indent_level -= 1

    def visit_shell_out_node(self, node: ShellOutNode):
        self.consume(f'{self._indent()}ShellOut')
        self.indent_level += 1
        node.text_node.accept(self)
        self.indent_level -= 1

    def visit_for_in_node(self, node: ForInNode):
        self.consume(f'{self._indent()}ForIn')
        self.indent_level += 1
        node.item.accept(self)
        node.items.accept(self)
        for n in node.suite:
            n.accept(self)
        self.indent_level -= 1

    def visit_name_node(self, node):
        self.consume(f'{self._indent()}{node.token.value}')

    def visit_symbol_node(self, node):
        self.consume(f'{self._indent()}@{node.token.value}')

    def visit_text_node(self, node):
        self.consume(f'{self._indent()}{node.token.value}')

    def visit_key_value_node(self, node: KeyValueNode):
        self.consume(f'{self._indent()}KV')
        self.indent_level += 1
        node.key_node.accept(self)
        node.value_node.accept(self)
        self.indent_level -= 1

    def visit_dict_node(self, node: DictNode):
        self.consume(f'{self._indent()}Dict')
        self.indent_level += 1
        for kv_node in node.kv_nodes:
            kv_node.accept(self)
        self.indent_level -= 1

    def visit_array_node(self, node: ArrayNode):
        self.consume(f'{self._indent()}Array')
        self.indent_level += 1
        for n in node.value_nodes:
            n.accept(self)
        self.indent_level -= 1

    def visit_string_node(self, node):
        self.consume(f'{self._indent()}{node.token.value}')

    def visit_number_node(self, node):
        self.consume(f'{self._indent()}{node.token.value}')

    def visit_bin_op_node(self, node: BinOpNode):
        self.consume(f'{self._indent()}BinOp({node.op_token.value})')
        self.indent_level += 1
        node.left_node.accept(self)
        node.right_node.accept(self)
        self.indent_level -= 1

    def visit_unary_op_node(self, node: UnaryOpNode):
        self.consume(f'{self._indent()}UnaryOp({node.op_token.value})')
        self.indent_level += 1
        node.operand_node.accept(self)
        self.indent_level -= 1

    def visit_group_node(self, node):
        node.grouped.accept(self)

    def _indent(self):
        return self.indent_level * self.indent_chars


def options_consumer_maker(options_parts, v):
    """
    This is to convert a dict representation to k=v representation
    """
    if v == ':':
        options_parts.append('=')
    elif v == ',':
        options_parts.append(' ')
    elif v not in ['{', '}'] and v.strip() != '':
        options_parts.append(v)
