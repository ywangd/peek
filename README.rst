====
Peek
====

.. image:: https://github.com/ywangd/peek/workflows/Peek/badge.svg
        :target: https://github.com/ywangd/peek

Peek is an interactive CLI tool for working with Elasticsearch clusters.
It is like `Kibana Console <https://www.elastic.co/guide/en/kibana/current/console-kibana.html>`_
running in terminal with additional features for tinkers.


Installation
------------

This project is currently under development and can be installed in development mode from the source repository.
Please note it requires Python 3.6+.

1. Clone the `repository <https://github.com/ywangd/peek>`_
2. Inside the project root directory, run ``pip install -e .``

The tool is now available with the ``peek`` command. Other than HTTP calls to Elasticsearch clusters, type ``help``
to get a list of builtin functions.

* Run ``make get-specs`` to pull API specs from the `Kibana project <https://github.com/elastic/kibana>`_.
  This enables auto-completions for APIs (WIP).
* Run tests with ``tox -e py38,flake8 -s true``

Features
--------

* Most features offered by Kibana Console, e.g. syntax highlighting, auto-formatting, auto-indent,
  auto-completion (WIP), par-editing, etc.
* Lightweight CLI tool
* Multiplex to multiple Elasticsearch clusters or multiple users/credentials of a single cluster
* Connect to `Elastic Cloud <https://cloud.elastic.co/>`_ with Cloud ID
* Multiple authentication schemes in a single terminal, including UserPass, API key, Token, SAML, OIDC, Kerberos, PKI
* Run-As support
* History
* Run file input in batch mode
* Extensible via external scripts

Credits
-------

