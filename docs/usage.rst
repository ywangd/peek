=====
Usage
=====

For basic usages, please refer to the `Sample Usages <../README.rst#sample-usages>`_ for a quick guide.
Here we provide a few more details which may become handy in certain situations.

The ``peekrc`` File
-------------------
The ``peekrc`` file takes configurations to customise some aspects of the program. A
`default <peek/peekrc>`_ version is provided as part of the project. It can be overriden
by users. Peek looks for user provided ``peekrc`` file in its config folder, which is
``$HOME/.config/peek`` on MacOS. The exact location of the config folder can be checked
by running the `config` builtin function inside Peek.

Useful config options
^^^^^^^^^^^^^^^^^^^^^
* ``swap_colour`` - Peek's default colour scheme works well with terminals using dark theme.
  For light themed terminals, set this option to ``True`` for better results.
* ``mouse_support`` - Mouse is not supported by default because it does not work well with
  scroll. However, it can be enabled by set this option to ``True``. Alternatively, it can
  also be toggled on the fly with key ``<F12>``.

Default Connection
^^^^^^^^^^^^^^^^^^
Peek starts with a default connection to ``http://localhost:9200`` with no credentials.
This is likely not suitable for real use cases. Hence it is possible to customise the
default connection in the ``peekrc`` file as the follows:

.. code-block:: ini

  [connection]
  hosts = example.com:9200
  username = admin-user
  use_ssl = True


Credentials
^^^^^^^^^^^
It is **not** recommended to put cleartext password in the ``peekrc`` file. Peek also
does not store cleartext password in any files. It by default attempts to use the system
keyring for password storage. For this, it will ask for permission to use the keyring.
By storing password in keyring, it avoids asking for password repetitively.
However, you can opt-out this behaviour by setting ``use_keyring = False`` in ``peekrc``
file. Peek also looks for the ``PEEK_PASSWORD`` environmental variable for password
and this is another way to avoid having to enter password many times. If both fails,
Peek will prompt for password.
Please note, API keys and tokens are treated differently. They are considered to be
more ephemeral and are stored in Peek's ``history`` sqlite file.


Connection and Session
----------------------

In one Peek *session*, we can have multiple *connections* to one or more Elasticsearch clusters.
Connections can be added or removed for a single session. A connection is created by specify
at least the ``hosts`` of the cluster. For secured cluster, relevant credentials are required
as well. Note by default, connection creation is purely local and does **not** automatically
test the connection. In another word, even if the remote host is down or the credentials are wrong,
a connection will still be created successfully. This behaviour is default because Peek always
launches with at least one connection (e.g. a commonly used one) for convenience. As a CLI tool,
it may also be launched and shutdown frequently. If connections are tested every time they are
created, it could add noticeable overhead since HTTP calls could be slow.

With above being said, it is possible to opt-in for connection test on creation. This can be
as requested via the ``test`` option to the ``connect`` function, e.g.:

.. code-block:: bash

  connect hosts='localhost:9200' test=true

This behaviour can also be enabled by default with ``test_connection = False`` in
the ``peekrc`` file.

For a single Peek session, we may end up having multiple connections. Sometimes, it is
useful if these connections can be restored when peek restarts. By default, peek saves
current session information on exit. But it does not restore it by default on start.
This can be enabled by setting ``auto_load_session = True``.
Note if an connection is specified explicitly on launch, session will not be restored
even with the above configuration. It is possible to manually load the last auto-saved
session with ``session load='__auto__'``. With the builtin ``session`` management function,
multiple sessions can be saved and restored at will.


Auto-Completion and API Spec Files
----------------------------------
Peek's auto-completion feature for Elasticsearch APIs relies on the API spec files published by the
`Kibana project <https://github.com/elastic/kibana>`_.
Peek however does not ship with these spec files.
To access these files, you can use one of the following options:

* If you have cloned Kibana's GitHub repository, simply configure ``kibana_dir`` in
  ``peekrc`` to point to the project root directory.
* Peek has a builtin function, ``_download_api_specs`` which download a release archive
  of Kibana and extract the relevant spec files into it's own config directory.

Kibana uses TypeScript to code the more advanced completion rules, e.g. Query DSL.
Peek's parsing of TypeScript is rather hacky. It is tested and works with v7.8 and
v7.9. But it may become unstable for Kibana's future releases. Therefore, Peek
caches the TypeScript completion rules in its own scripting format (look into
``extended_specs.es`` in its config directory for details). To force Peek parse
the TypeScript files again, please remove the cache file. This behaviour can also be
turned off with ``cache_extended_api_specs = False`` in ``peekrc`` file.
