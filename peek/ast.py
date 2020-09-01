from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from typing import List, Union

from peek.common import PeekToken


class Visitor(metaclass=ABCMeta):

    def __init__(self):
        self._consumers = []

    def visit_es_api_call_node(self, node):
        raise NotImplementedError()

    def visit_func_call_node(self, node):
        raise NotImplementedError()

    def visit_let_node(self, node):
        raise NotImplementedError()

    def visit_shell_out_node(self, node):
        raise NotImplementedError()

    def visit_for_in_node(self, node):
        raise NotImplementedError()

    def visit_name_node(self, node):
        raise NotImplementedError()

    def visit_symbol_node(self, node):
        raise NotImplementedError()

    def visit_text_node(self, node):
        raise NotImplementedError()

    def visit_key_value_node(self, node):
        raise NotImplementedError()

    def visit_dict_node(self, node):
        raise NotImplementedError()

    def visit_array_node(self, node):
        raise NotImplementedError()

    def visit_string_node(self, node):
        raise NotImplementedError()

    def visit_number_node(self, node):
        raise NotImplementedError()

    def visit_bin_op_node(self, node):
        raise NotImplementedError()

    def visit_unary_op_node(self, node):
        raise NotImplementedError()

    def visit_group_node(self, node):
        raise NotImplementedError()

    def consume(self, *args, **kwargs):
        if not self._consumers:
            raise IndexError('No consumer')
        self._consumers[-1](*args, **kwargs)

    @contextmanager
    def consumer(self, c):
        self._push_consumer(c)
        try:
            yield
        finally:
            self._pop_consumer()

    def _push_consumer(self, consumer):
        self._consumers.append(consumer)

    def _pop_consumer(self):
        if not self._consumers:
            raise IndexError('No consumer')
        self._consumers = self._consumers[:-1]


class Node(metaclass=ABCMeta):

    @abstractmethod
    def accept(self, visitor: Visitor):
        pass

    @abstractmethod
    def tokens(self):
        pass

    def __str__(self):
        return self.tokens()[0].value

    def __repr__(self):
        return repr(str(self))


class NameNode(Node):

    def __init__(self, token: PeekToken):
        self.token = token

    def accept(self, visitor: Visitor):
        visitor.visit_name_node(self)

    def tokens(self):
        return [self.token]


class TextNode(Node):

    def __init__(self, token: PeekToken):
        self.token = token

    def accept(self, visitor: Visitor):
        visitor.visit_text_node(self)

    def tokens(self):
        return [self.token]


class SymbolNode(Node):

    def __init__(self, token: PeekToken):
        self.token = token

    def accept(self, visitor: Visitor):
        visitor.visit_symbol_node(self)

    def tokens(self):
        return [self.token]


class KeyValueNode(Node):

    def __init__(self, key_node: Node, value_node: Node):
        self.key_node = key_node
        self.value_node = value_node

    def accept(self, visitor: Visitor):
        visitor.visit_key_value_node(self)

    def tokens(self):
        return self.key_node.tokens() + self.value_node.tokens()

    def __str__(self):
        return f'{self.key_node}:{self.value_node}'


class DictNode(Node):

    def __init__(self, kv_nodes: List[KeyValueNode]):
        self.kv_nodes = kv_nodes

    def accept(self, visitor: Visitor):
        visitor.visit_dict_node(self)

    def tokens(self):
        tokens = []
        for n in self.kv_nodes:
            tokens += n.tokens()
        return tokens

    def __str__(self):
        parts = ['{']
        for i, n in enumerate(self.kv_nodes):
            parts.append(str(n))
            if i < len(self.kv_nodes) - 1:
                parts.append(',')
        parts.append('}')
        return ''.join(parts)


class ArrayNode(Node):

    def __init__(self, value_nodes: List[Node]):
        self.value_nodes = value_nodes

    def accept(self, visitor: Visitor):
        return visitor.visit_array_node(self)

    def tokens(self):
        tokens = []
        for n in self.value_nodes:
            tokens += n.tokens()
        return tokens

    def __str__(self):
        parts = ['[']
        for i, n in enumerate(self.value_nodes):
            parts.append(str(n))
            if i < len(self.value_nodes) - 1:
                parts.append(',')
        parts.append(']')
        return ''.join(parts)


class StringNode(Node):

    def __init__(self, token: PeekToken):
        self.token = token

    def accept(self, visitor: Visitor):
        visitor.visit_string_node(self)

    def tokens(self):
        return [self.token]


class NumberNode(Node):

    def __init__(self, token: PeekToken):
        self.token = token

    def accept(self, visitor: Visitor):
        visitor.visit_number_node(self)

    def tokens(self):
        return [self.token]


class UnaryOpNode(Node):

    def __init__(self, op_token: PeekToken, operand_node: Node):
        self.op_token = op_token
        self.operand_node = operand_node

    def accept(self, visitor: Visitor):
        visitor.visit_unary_op_node(self)

    def tokens(self):
        tokens = [self.op_token]
        tokens += self.operand_node.tokens()
        return tokens


class BinOpNode(Node):

    def __init__(self, op_token: PeekToken, left_node: Node, right_node: Node):
        self.op_token = op_token
        self.left_node = left_node
        self.right_node = right_node

    def accept(self, visitor: Visitor):
        visitor.visit_bin_op_node(self)

    def tokens(self):
        tokens = self.left_node.tokens()
        tokens.append(self.op_token)
        tokens += self.right_node.tokens()
        return tokens

    def __str__(self):
        return f'{self.left_node} {self.op_token.value} {self.right_node}'


class GroupNode(Node):
    """
    A decorator node that indicates there are parenthesis around the node
    """

    def __init__(self, node: Node, paren_left: PeekToken, paren_right: PeekToken):
        self.grouped = node
        self.paren_left = paren_left
        self.paren_right = paren_right

    def accept(self, visitor: Visitor):
        visitor.visit_group_node(self)

    def tokens(self):
        tokens = [self.paren_left]
        tokens += self.grouped.tokens()
        tokens.append(self.paren_right)
        return tokens

    def __str__(self):
        return f'({self.grouped})'


class EsApiCallNode(Node, metaclass=ABCMeta):

    def __init__(self, method_node: NameNode, path_node: Union[TextNode, GroupNode], options_node: DictNode):
        self.method_node = method_node
        self.path_node = path_node
        self.options_node = options_node

    def accept(self, visitor: Visitor):
        visitor.visit_es_api_call_node(self)

    def tokens(self):
        tokens = self.method_node.tokens() + self.path_node.tokens()
        tokens += self.options_node.tokens()
        return tokens

    @property
    def method(self):
        return self.method_node.token.value.upper()

    @property
    def path(self):
        if isinstance(self.path_node, TextNode):
            path = self.path_node.token.value
            return path if path.startswith('/') else ('/' + path)
        else:
            raise ValueError('simple path is only available when path node is simple text')


class EsApiCallInlinePayloadNode(EsApiCallNode):

    def __init__(self, method_node: NameNode, path_node: Union[TextNode, GroupNode], options_node: DictNode,
                 dict_nodes: List[DictNode]):
        super().__init__(method_node, path_node, options_node)
        self.dict_nodes = dict_nodes

    def tokens(self):
        tokens = super().tokens()
        for n in self.dict_nodes:
            tokens += n.tokens
        return tokens

    def __str__(self):
        parts = [str(self.method_node), ' ', str(self.path_node), ' ', str(self.options_node), '\n']
        for n in self.dict_nodes:
            parts.append(str(n))
            parts.append('\n')
        return ''.join(parts)


class EsApiCallFilePayloadNode(EsApiCallNode):

    def __init__(self, method_node: NameNode, path_node: Union[TextNode, GroupNode], options_node: DictNode,
                 file_node: TextNode):
        super().__init__(method_node, path_node, options_node)
        self.file_node = file_node

    def tokens(self):
        tokens = super().tokens()
        tokens.append(self.file_node.token)
        return tokens

    def __str__(self):
        parts = [str(self.method_node), ' ', str(self.path_node), ' ', str(self.options_node), '\n',
                 '@', str(self.file_node), '\n']
        return ''.join(parts)


class FuncCallNode(Node):

    def __init__(self, name_node: Node, symbols_node: ArrayNode, args_node: ArrayNode,
                 kwargs_node: DictNode, is_stmt=True):
        self.name_node = name_node
        self.symbols_node = symbols_node
        self.args_node = args_node
        self.kwargs_node = kwargs_node
        self.is_stmt = is_stmt

    def accept(self, visitor: Visitor):
        visitor.visit_func_call_node(self)

    def tokens(self):
        tokens = self.name_node.tokens()
        tokens += self.symbols_node.tokens()
        tokens += self.args_node.tokens()
        tokens += self.kwargs_node.tokens()
        return tokens

    def __str__(self):
        parts = [str(self.name_node), ' ',
                 str(self.symbols_node), ' ',
                 str(self.args_node), ' ',
                 str(self.kwargs_node), '\n' if self.is_stmt else '']
        return ''.join(parts)


class LetNode(Node):

    def __init__(self, assignments_node: DictNode):
        self.assignments_node = assignments_node

    def accept(self, visitor: Visitor):
        visitor.visit_let_node(self)

    def tokens(self):
        return self.assignments_node.tokens()

    def __str__(self):
        parts = ['let', ' ',
                 str(self.assignments_node), '\n']
        return ''.join(parts)


class ForInNode(Node):

    def __init__(self, item: NameNode, items: Node, suite: List[Node]):
        self.item = item
        self.items = items
        self.suite = suite

    def accept(self, visitor: Visitor):
        visitor.visit_for_in_node(self)

    def tokens(self):
        tokens = self.item.tokens() + self.items.tokens()
        for node in self.suite:
            tokens += node.tokens()
        return tokens

    def __str__(self):
        parts = [
            'for ',
            self.item.token.value,
            ' in ',
            str(self.items),
            '{\n'
        ]
        for node in self.suite:
            parts.append(str(node))
        parts.append('}\n')
        return ''.join(parts)


class ShellOutNode(Node):

    def __init__(self, text_node: TextNode):
        self.text_node = text_node

    def accept(self, visitor: Visitor):
        visitor.visit_shell_out_node(self)

    @property
    def command(self):
        return self.text_node.token.value

    def tokens(self):
        return self.text_node.tokens()

    def __str__(self):
        parts = ['!', ' ',
                 str(self.text_node), '\n']
        return ''.join(parts)
