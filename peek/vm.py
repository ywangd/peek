import ast
import itertools
import json
import logging
import operator
import os
import sys
from numbers import Number
from subprocess import Popen

from pygments.token import Name

from peek.ast import Visitor, EsApiCallNode, DictNode, KeyValueNode, ArrayNode, NumberNode, \
    StringNode, Node, FuncCallNode, NameNode, TextNode, ShellOutNode, EsApiCallInlinePayloadNode, \
    EsApiCallFilePayloadNode, GroupNode, BinOpNode, UnaryOpNode, SymbolNode, LetNode, ForInNode
from peek.errors import PeekError
from peek.natives import EXPORTS
from peek.visitors import Ref

_logger = logging.getLogger(__name__)


def dot(left_operand, right_operand):
    if isinstance(left_operand, dict):
        if right_operand in left_operand:
            return left_operand[right_operand]
        else:
            raise PeekError(f'Value {left_operand!r} does not have key {right_operand!r}')
    elif isinstance(left_operand, list):
        if isinstance(right_operand, int):
            return left_operand[right_operand]
        else:
            raise PeekError(f'Cannot index array {left_operand!r} with non-integer value: {right_operand!r}')
    else:
        raise PeekError(f'Value {left_operand!r} must be either an array or dict')


def add(left_operand, right_operand):
    if isinstance(left_operand, str) and isinstance(right_operand, Number):
        return operator.add(left_operand, str(right_operand))
    elif isinstance(left_operand, Number) and isinstance(right_operand, str):
        return operator.add(str(left_operand), right_operand)
    else:
        return operator.add(left_operand, right_operand)


_BIN_OP_FUNCS = {
    '+': add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
    '%': operator.mod,
    '.': dot,
}

_UNARY_OP_FUNCS = {
    '+': operator.pos,
    '-': operator.neg,
}


class PeekVM(Visitor):

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.context = {}
        self.builtins = EXPORTS
        if self.app.config.as_bool('load_extension'):
            self._load_extensions()
        self.es_api_payload_line = []
        self.func_args = []
        self.func_kwargs = {}

    @property
    def functions(self):
        return {k: v for k, v in itertools.chain(self.builtins.items(), self.context.items()) if callable(v)}

    def execute_node(self, node: Node):
        node.accept(self)

    def visit_es_api_call_node(self, node: EsApiCallNode):
        if isinstance(node.path_node, TextNode):
            path = node.path
        else:
            path_ref = Ref()
            with self.consumer(lambda v: path_ref.set(v)):
                node.path_node.accept(self)
            path = path_ref.get()
            path = path if path.startswith('/') else ('/' + path)

        options = Ref()
        self.push_consumer(lambda v: options.set(v))
        self._do_visit_dict_node(node.options_node)
        self.pop_consumer()
        options = options.get()

        if isinstance(node, EsApiCallInlinePayloadNode):
            dicts = []
            self.push_consumer(lambda v: dicts.append(v))
            for dict_node in node.dict_nodes:
                dict_node.accept(self)
            self.pop_consumer()
            lines = [json.dumps(d) for d in dicts]
            payload = ('\n'.join(lines) + '\n') if lines else None
        elif isinstance(node, EsApiCallFilePayloadNode):
            f = Ref()
            self.push_consumer(lambda v: f.set(v))
            node.file_node.accept(self)
            self.pop_consumer()
            with open(os.path.expanduser(f.get())) as ins:
                payload = ins.read()
                if not payload.endswith('\n'):
                    payload += '\n'
        else:
            raise ValueError(f'Unknown node: {node!r}')

        conn = options.pop('conn') if 'conn' in options else None
        headers = options.pop('headers') if 'headers' in options else {}
        xoid = options.pop('xoid') if 'xoid' in options else None
        if xoid:
            headers['x-opaque-id'] = str(xoid)
        runas = options.pop('runas') if 'runas' in options else None
        if runas is not None:
            headers['es-security-runas-user'] = runas
        if conn is not None:
            es_client = self.app.es_client_manager.get_client(conn)
        else:
            es_client = self.app.es_client_manager.current
        if options:
            self.app.display.error(f'Unknown options: {options}')
            return

        try:
            response = es_client.perform_request(node.method, path, payload, headers=headers if headers else None)
            self.context['_'] = _maybe_jsonify(response)
            self.app.display.info(response, header_text=self._get_header_text(conn, runas))
        except Exception as e:
            if getattr(e, 'info', None) and isinstance(getattr(e, 'status_code', None), int):
                self.context['_'] = _maybe_jsonify(e.info)
                self.app.display.info(e.info, header_text=self._get_header_text(conn, runas))
            else:
                self.app.display.error(e, header_text=self._get_header_text(conn, runas))
                _logger.exception(f'Error on ES API call: {node!r}')

    def visit_func_call_node(self, node: FuncCallNode):
        if isinstance(node.name_node, NameNode):
            func = self.get_value(node.name_node.token.value)
        else:
            func_ref = Ref()
            self.push_consumer(lambda v: func_ref.set(v))
            node.name_node.accept(self)
            self.pop_consumer()
            func = func_ref.get()
        if not callable(func):
            raise PeekError(f'{node.name_node!r} is not a callable, but {func!r}')

        func_symbols = Ref()
        self.push_consumer(lambda v: func_symbols.set(v))
        node.symbols_node.accept(self)
        self.pop_consumer()

        func_args = Ref()
        self.push_consumer(lambda v: func_args.set(v))
        node.args_node.accept(self)
        self.pop_consumer()

        for kv_node in node.kwargs_node.kv_nodes:
            assert isinstance(kv_node.key_node, NameNode), f'{kv_node.key_node!r}'
        func_kwargs = Ref()
        self.push_consumer(lambda v: func_kwargs.set(v))
        self._do_visit_dict_node(node.kwargs_node, resolve_key_name=False)
        self.pop_consumer()
        kwargs = func_kwargs.get()
        if func_symbols.get():
            kwargs['@'] = func_symbols.get()
        try:
            result = func(self.app, *func_args.get(), **kwargs)
            if node.is_stmt:
                self.app.display.info(result)
            else:
                self.consume(result)
        except Exception as e:
            _logger.exception(f'Error on invoking function: {node.name_node!r}')
            self.app.display.error(e)

    def visit_let_node(self, node: LetNode):
        for kv_node in node.assignments_node.kv_nodes:
            lhs_chain = []
            self.push_consumer(lambda v: lhs_chain.append(v))
            self._unwind_lhs(kv_node.key_node)
            self.pop_consumer()

            rhs = Ref()
            self.push_consumer(lambda v: rhs.set(v))
            kv_node.value_node.accept(self)
            self.pop_consumer()

            if len(lhs_chain) == 1:
                self.context[lhs_chain[0]] = rhs.get()
            else:
                if not lhs_chain[0] in self.context:
                    raise PeekError(f'Unknown name: {lhs_chain[0]!r}')
                lhs = self.context[lhs_chain[0]]
                for x in lhs_chain[1:-1]:
                    if isinstance(lhs, dict) or (isinstance(lhs, list) and isinstance(x, int)):
                        lhs = lhs[x]
                    else:
                        raise PeekError(f'Invalid lhs for assignment: {".".join(lhs_chain)}')

                x = lhs_chain[-1]
                if isinstance(lhs, dict) or (isinstance(lhs, list) and isinstance(x, int)):
                    lhs[x] = rhs.get()
                else:
                    raise PeekError(f'Invalid lhs for assignment: {lhs_chain}')

    def visit_shell_out_node(self, node: ShellOutNode):
        try:
            input_fd = self.app.prompt.input.fileno()
        except AttributeError:
            input_fd = sys.stdin.fileno()
        try:
            output_fd = self.app.prompt.output.fileno()
        except AttributeError:
            output_fd = sys.stdout.fileno()
        p = Popen(node.command, shell=True, stdin=input_fd, stdout=output_fd)
        p.wait()

    def visit_for_in_node(self, node: ForInNode):
        var_name = node.item.token.value
        items_ref = Ref()
        self.push_consumer(lambda v: items_ref.set(v))
        node.items.accept(self)
        self.pop_consumer()
        items = items_ref.get()
        if not isinstance(items, list):
            raise PeekError(f'For in loop must operator over a list, got {items!r}')

        for i in items:
            self.context[var_name] = i
            for n in node.suite:
                n.accept(self)

    def visit_key_value_node(self, node: KeyValueNode):
        node.key_node.accept(self)
        node.value_node.accept(self)

    def visit_name_node(self, node: NameNode):
        v = self.get_value(node.token.value)
        self.consume(v)

    def visit_symbol_node(self, node: SymbolNode):
        self.consume(node.token.value)

    def visit_string_node(self, node: StringNode):
        self.consume(ast.literal_eval(node.token.value))

    def visit_number_node(self, node: NumberNode):
        self.consume(ast.literal_eval(node.token.value))

    def visit_dict_node(self, node: DictNode):
        self._do_visit_dict_node(node, resolve_key_name=True)

    def visit_array_node(self, node: ArrayNode):
        values = []
        self.push_consumer(lambda v: values.append(v))
        for node in node.value_nodes:
            node.accept(self)
        self.pop_consumer()
        self.consume(values)

    def visit_text_node(self, node: TextNode):
        if node.token.ttype is Name.Builtin:
            self.consume({'true': True, 'false': False, 'null': None}[node.token.value])
        else:
            self.consume(node.token.value)

    def visit_bin_op_node(self, node: BinOpNode):
        left_operand = Ref()
        self.push_consumer(lambda v: left_operand.set(v))
        node.left_node.accept(self)
        self.pop_consumer()

        right_operand = Ref()
        self.push_consumer(lambda v: right_operand.set(v))
        node.right_node.accept(self)
        self.pop_consumer()

        op_func = _BIN_OP_FUNCS.get(node.op_token.value, None)
        if op_func is None:
            raise PeekError(f'Unknown binary operator: {node.op_token.value!r}')
        self.consume(op_func(left_operand.get(), right_operand.get()))

    def visit_unary_op_node(self, node: UnaryOpNode):
        operand = Ref()
        self.push_consumer(lambda v: operand.set(v))
        node.operand_node.accept(self)
        self.pop_consumer()

        op_func = _UNARY_OP_FUNCS.get(node.op_token.value, None)
        if op_func is None:
            raise PeekError(f'Unknown unary operator: {node.op_token.value!r}')
        self.consume(op_func(operand.get()))

    def visit_group_node(self, node: GroupNode):
        node.grouped.accept(self)

    def _do_visit_dict_node(self, node: DictNode, resolve_key_name=False):
        assert isinstance(node, DictNode)
        keys = []
        values = []
        self.push_consumer(lambda v: keys.append(v))
        for kv_node in node.kv_nodes:
            if resolve_key_name or not isinstance(kv_node.key_node, NameNode):
                kv_node.key_node.accept(self)
            else:
                self.consume(kv_node.key_node.token.value)
            self.push_consumer(lambda v: values.append(v))
            kv_node.value_node.accept(self)
            self.pop_consumer()
        self.pop_consumer()
        assert len(keys) == len(values), f'{keys!r}, {values!r}'
        self.consume(dict(zip(keys, values)))

    def get_value(self, name):
        value = self.builtins.get(name)
        if value is None:
            value = self.context.get(name)
        if value is None:
            raise PeekError(f'Unknown name: {name!r}')
        return value

    def _unwind_lhs(self, node: Node):
        if isinstance(node, NameNode):
            self.consume(node.token.value)
        elif isinstance(node, BinOpNode):
            if node.op_token.value != '.':
                raise PeekError(f'lhs can only have variable and dot notation, but got {node!r}')
            self._unwind_lhs(node.left_node)
            node.right_node.accept(self)
        else:
            raise PeekError(f'lhs can only have variable and dot notation, but got {node!r}')

    def _load_extensions(self):
        """
        Load extra variables from external paths
        """
        extension_path = self.app.config['extension_path']
        if not extension_path:
            return

        sys_path = sys.path[:]
        try:
            for p in extension_path.split(':'):
                if os.path.isfile(p):
                    self._load_one_extension(p)
                elif os.path.isdir(p):
                    for f in os.listdir(p):
                        if not f.endswith('.py'):
                            continue
                        self._load_one_extension(os.path.join(p, f))
                else:
                    _logger.warning(f'Cannot load extension path: {p}')
        finally:
            sys.path = sys_path

    def _load_one_extension(self, p):
        _logger.debug(f'Loading extension: {p!r}')
        import importlib
        fields = os.path.splitext(p)
        if len(fields) != 2 or fields[1] != '.py':
            _logger.warning(f'Extension must be python files, got: {p!r}')
            return
        sys.path.insert(0, os.path.dirname(fields[0]))
        try:
            m = importlib.import_module(os.path.basename(fields[0]))
            exports = getattr(m, 'EXPORTS', None)
            if isinstance(exports, dict):
                self.context.update(exports)
                _logger.info(f'Loaded extension: {p!r}')
            else:
                _logger.warning(f'Ignore extension {p!r} since EXPORTS is not a dict, but: {exports!r}')
        except Exception as e:
            _logger.error(f'Error on loading extension: {p!r}, {e}')
            _logger.exception(f'Error on loading extension: {p!r}')

    def _get_header_text(self, conn, runas):
        parts = []
        if conn is not None:
            parts.append(f'conn={conn!r}')
        if runas is not None:
            parts.append(f'runas={runas!r}')
        return ' '.join(parts)


def _maybe_jsonify(r):
    try:
        return json.loads(r)
    except Exception:
        return r
