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

    assert visitor.visit(nodes[0]) == '''get / conn=1 runas="foo"
{"a":"b","q":[1,2]}
'''
    nodes = parser.parse('get ("foo" + "/" + 42 + "/" + 1)')
    assert visitor.visit(nodes[0]) == 'get ("foo"+"/"+42+"/"+1)\n'


def test_formatting_api_call_pretty(parser):
    visitor = FormattingVisitor(pretty=True)
    nodes = parser.parse('''get / conn =  1 runas = "foo"
{
  "a"   :
"b", "q": [
1,
2]}''')

    assert visitor.visit(nodes[0]) == '''get / conn=1 runas="foo"
{
  "a": "b",
  "q": [
    1,
    2
  ]
}
'''


def test_formatting_func_call(parser):
    visitor = FormattingVisitor()
    nodes = parser.parse('''f @abc 1 "a" b=a foo="bar"''')

    assert visitor.visit(nodes[0]) == '''f @abc 1 "a" b=a foo="bar"'''


def test_formatting_for_in_compact(parser):
    visitor = FormattingVisitor(pretty=False)
    nodes = parser.parse('''for a in [1, 2, 3] {
        echo a
        for b in c {
            echo b
            let x = b
        }
        echo a + 1
    }''')

    assert visitor.visit(nodes[0]) == '''for a in [1,2,3] {
  echo a
  for b in c {
    echo b
    let x=b
  }
  echo a+1
}'''


def test_formatting_pretty(parser):
    visitor = FormattingVisitor(pretty=True)
    nodes = parser.parse('''for x in [1,2] {
    let a = { 1: 2, 3: 4, 'foo': [42, "hello"]}
    echo a x
    for y in c {
        echo [1, 3, 5] b={'foo': 42, "bar": [6, 7, [8, 9]]}
        GET /path
        {"foo": {"q": [1, 2,{'x': [3, "5", {}]}]}}
    }
}''')
    assert visitor.visit(nodes[0]) == '''for x in [
  1,
  2
] {
  let a={
      1: 2,
      3: 4,
      'foo': [
        42,
        "hello"
      ]
    }
  echo a x
  for y in c {
    echo [
        1,
        3,
        5
      ] b={
        'foo': 42,
        "bar": [
          6,
          7,
          [
            8,
            9
          ]
        ]
      }
    GET /path
    {
      "foo": {
        "q": [
          1,
          2,
          {
            'x': [
              3,
              "5",
              {}
            ]
          }
        ]
      }
    }

  }
}'''


def test_formatting_looped_api_calls(parser):
    nodes = parser.parse('''for i in range(@foo @bar 1 10 a=4 b=2) {
  POST test-1/_doc
  { "tag": i }
  POST test-2/_doc
  { "tag": i + 1}
}
''')

    assert FormattingVisitor(pretty=True).visit(nodes[0]) == '''for i in range(@foo, @bar, 1, 10, a=4, b=2) {
  POST test-1/_doc
  {
    "tag": i
  }

  POST test-2/_doc
  {
    "tag": i+1
  }

}'''

    assert FormattingVisitor(pretty=False).visit(nodes[0]) == '''for i in range(@foo,@bar,1,10,a=4,b=2) {
  POST test-1/_doc
  {"tag":i}

  POST test-2/_doc
  {"tag":i+1}

}'''


def test_tree_formatting(parser):
    visitor = TreeFormattingVisitor()
    nodes = parser.parse('''f @abc 1 "a" b=a foo="bar" 1 * 2 + (3-2) * 5 / 6
get ("hello" + 42 + "world")''')
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

    assert visitor.visit(nodes[1]) == '''EsApiStmt
  get
  BinOp(+)
    BinOp(+)
      "hello"
      42
    "world"
  Dict'''


def test_tree_formatting_func_expr_chain(parser):
    visitor = TreeFormattingVisitor()
    nodes = parser.parse('''f a.@b(1)''')
    assert "FuncExpr('a . b')" in visitor.visit(nodes[0])


def test_tree_formatting_for_in(parser):
    visitor = TreeFormattingVisitor()
    nodes = parser.parse('''for a in [1, 2, 3] {
    echo a
    for b in c {
        echo b
    }
    echo a + 1
}
for x in y {}''')
    assert visitor.visit(nodes[0]) == '''ForIn
  a
  Array
    1
    2
    3
  FuncStmt('echo')
    Array
    Array
      a
    Dict
  ForIn
    b
    c
    FuncStmt('echo')
      Array
      Array
        b
      Dict
  FuncStmt('echo')
    Array
    Array
      BinOp(+)
        a
        1
    Dict'''

    assert visitor.visit(nodes[1]) == '''ForIn
  x
  y'''
