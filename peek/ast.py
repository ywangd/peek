from abc import ABCMeta, abstractmethod
from typing import List

from peek.common import PeekToken


class Visitor(metaclass=ABCMeta):

    def __init__(self):
        self._consumers = []

    def visit_es_api_call_node(self, node):
        raise NotImplementedError()

    def visit_func_call_node(self, node):
        raise NotImplementedError()

    def visit_name_node(self, node):
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

    def push_consumer(self, consumer):
        self._consumers.append(consumer)

    def pop_consumer(self):
        if not self._consumers:
            raise IndexError(f'No consumer')
        self._consumers = self._consumers[:-1]

    def consume(self, *args, **kwargs):
        if not self._consumers:
            raise IndexError(f'No consumer')
        self._consumers[-1](*args, **kwargs)


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

    def accept(self, visitor):
        visitor.visit_name_node(self)

    def tokens(self):
        return [self.token]


class TextNode(Node):

    def __init__(self, token: PeekToken):
        self.token = token

    def accept(self, visitor):
        visitor.visit_text_node(self)

    def tokens(self):
        return [self.token]


class KeyValueNode(Node):

    def __init__(self, key_node: Node, value_node: Node):
        self.key_node = key_node
        self.value_node = value_node

    def accept(self, visitor):
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


class EsApiCallNode(Node):

    def __init__(self,
                 method_node: NameNode, path_node: NameNode,
                 options_node: DictNode, dict_nodes: List[DictNode]):
        self.method_node = method_node
        self.path_node = path_node
        self.options_node = options_node
        self.dict_nodes = dict_nodes

    def accept(self, visitor):
        visitor.visit_es_api_call_node(self)

    def tokens(self):
        tokens = self.method_node.tokens() + self.path_node.tokens()
        tokens += self.options_node.tokens()
        for n in self.dict_nodes:
            tokens += n.tokens
        return tokens

    @property
    def method(self):
        return self.method_node.token.value.upper()

    @property
    def path(self):
        path = self.path_node.token.value
        return path if path.startswith('/') else ('/' + path)

    def __str__(self):
        parts = [str(self.method_node), ' ', str(self.path_node), ' ', str(self.options_node), '\n']
        for n in self.dict_nodes:
            parts.append(str(n))
            parts.append('\n')
        return ''.join(parts)


class FuncCallNode(Node):

    def __init__(self, name_node: NameNode, args_node: ArrayNode, kwargs_node: DictNode):
        self.name_node = name_node
        self.args_node = args_node
        self.kwargs_node = kwargs_node

    def accept(self, visitor: Visitor):
        visitor.visit_func_call_node(self)

    def tokens(self):
        tokens = self.name_node.tokens()
        tokens += self.args_node.tokens()
        tokens += self.kwargs_node.tokens()
        return tokens

    @property
    def func_name(self):
        return self.name_node.token.value

    def __str__(self):
        parts = [str(self.name_node), ' ', str(self.args_node), ' ', str(self.kwargs_node), '\n']
        return ''.join(parts)