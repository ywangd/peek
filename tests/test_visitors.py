import pytest

from peek.parser import PeekParser
from peek.visitors import FormattingVisitor


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

    assert '''f @abc 1 "a" b=a foo="bar"''' == visitor.visit(nodes[0])
