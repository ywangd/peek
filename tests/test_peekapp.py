#!/usr/bin/env python

"""Tests for `peek` package."""

import pytest

from peek.peekapp import PeekApp


@pytest.fixture
def response():
    """Sample pytest fixture.

    See more at: http://doc.pytest.org/en/latest/fixture.html
    """
    # import requests
    # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


def test_content(response):
    """Sample pytest test function with the pytest fixture as an argument."""
    # from bs4 import BeautifulSoup
    # assert 'GitHub' in BeautifulSoup(response.content).title.string


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
        r'''conn [] {foo:bar}
''',
        r'''get abc {}
''',
    ]
