#!/usr/bin/env python

"""Tests for `peek` package."""

from peek.peekapp import PeekApp


def test_multiple_stmts():
    text = """get abc

post abc/_doc
{ "foo":
         "bar"
}

conn foo=bar
get abc
"""
    nodes = []
    peek = PeekApp(batch_mode=True, extra_config_options=('log_level=None',))
    peek.execute_node = lambda stmt: nodes.append(stmt)
    peek.process_input(text)

    for n in nodes:
        print(n)

    assert [str(n) for n in nodes] == [
        r'''get abc {}
''',
        r'''post abc/_doc {}
{"foo":"bar"}
''',
        r'''conn [] [] {foo:bar}
''',
        r'''get abc {}
''',
    ]
