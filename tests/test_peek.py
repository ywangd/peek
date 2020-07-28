#!/usr/bin/env python

"""Tests for `peek` package."""

import pytest

from peek.peek import Peek


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


def test_multiple_commands():
    text = """get abc

post abc/_doc
{ "foo":
         "bar"
}

%conn foo=bar
get abc
"""
    batches = []
    peek = Peek(batch_mode=True)
    peek.execute_command = lambda buf: batches.append(buf)
    peek.process_input(text)

    assert batches == [
        'get abc\n',
        'post abc/_doc\n{ "foo":\n         "bar"\n}\n',
        '%conn foo=bar\n',
        'get abc\n',
    ]
