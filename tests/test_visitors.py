import pytest

from peek.parser import PeekParser
from peek.visitors import FormattingVisitor, TreeFormattingVisitor


@pytest.fixture
def parser():
    return PeekParser()


def test_formatting_api_call_compact(parser):
    visitor = FormattingVisitor()

    nodes = parser.parse('''get / conn =  1 runas = "foo"
{
  "a"   :
"b", "q": [
1,
2]}''')

    assert '''get / conn=1 runas="foo"
{"a":"b","q":[1,2]}
''' == visitor.visit(nodes[0])


def test_formatting_api_call_pretty(parser):
    visitor = FormattingVisitor(pretty=True)

    nodes = parser.parse('''get / conn =  1 runas = "foo"
{
  "a"   :
"b", "q": [
1,
2]}''')

    assert '''get / conn=1 runas="foo"
{
  "a": "b",
  "q": [
    1,
    2
  ]
}
''' == visitor.visit(nodes[0])


def test_formatting_func_call(parser):
    visitor = FormattingVisitor()
    nodes = parser.parse('''f @abc 1 "a" b=a foo="bar"''')

    assert visitor.visit(nodes[0]) == '''f @abc 1 "a" b=a foo="bar"'''


def test_tree_formatting(parser):
    visitor = TreeFormattingVisitor()
    nodes = parser.parse('''f @abc 1 "a" b=a foo="bar" 1 * 2 + (3-2) * 5 / 6''')
    assert visitor.visit(nodes[0]) == '''FuncStmt('f')
  Array
    @abc
  Array
    1
    "a"
    BinOp(+)
      BinOp(*)
        1
        2
      BinOp(/)
        BinOp(*)
          BinOp(-)
            3
            2
          5
        6
  Dict
    KV
      b
      a
    KV
      foo
      "bar"'''


def test_tree_formatting_func_expr_chain(parser):
    visitor = TreeFormattingVisitor()
    nodes = parser.parse('''f a.@b(1)''')
    assert "FuncExpr('a . b')" in visitor.visit(nodes[0])
