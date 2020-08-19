====
peek
====

.. image:: https://github.com/ywangd/peek/workflows/Peek/badge.svg
        :target: https://github.com/ywangd/peek

Peek is an interactive CLI tool for working with one or more elasticsearch clusters.
It is like `Kibana Console <https://www.elastic.co/guide/en/kibana/current/console-kibana.html>`_
running in terminal.


Installation
------------

This project is currently under development and it can be installed in development mode from the source repository.
Please note it requires Python 3.6+.

1. Clone the `repository <https://github.com/ywangd/peek>`_
2. Inside the project root directory, run ``pip install -e .``

The tool is now available with the ``peek`` command. Other than HTTP calls to elasticsearch clusters, type ``help``
to get a list of builtin functions.

Run tests with ``tox -e py38``

Features
--------

* Most features offered by Kibana Console, e.g. syntax highlighting, auto-formatting, auto-indent,
  auto-completion (WIP), par-editing, etc.
* Lightweight CLI tool
* Multiplexing to multiple elasticsearch clusters at the same time or multiple users of a single cluster
* Connection to `Elastic Cloud <https://cloud.elastic.co/>`_ with Cloud ID
* Multiple authentication schemes in a single terminal, including UserPass, API key, Token, SAML, OIDC, Kerberos, PKI
* Support runas
* History
* Run file input in batch mode
* Extensible via external scripts

Credits
-------

