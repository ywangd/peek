=====
Usage
=====

For basic usages, please refer to the `Sample Usages <../README.rst#sample-usages>`_ for a quick guide.
Here we provide a few more details which may become handy in certain situations.

The CLI interface
------------------
Peek can work in both interactive or batch mode. Without an input file, Peek starts in the
interactive mode. Otherwise, it runs in batch mode and execute the input file. The input
file can be a pipe so that Peek can be used as part of an IO pipeline.

In interactive mode, a blank line is normally required to trigger execution of a HTTP call.
This is necessary because it is not always possible to tell whether Peek should wait
for more payload lines. For an example, the ``PUT _bulk`` API can take a arbitrary
number of lines as its payload. In contrast, functions are expected to be a single line
and blank line is not needed to trigger their execution.

However, the blank line is *not* always required if there are other
ways that can mark the end of a HTTP call. For example:

.. code-block:: javascript

  GET _search  // no blank line is needed after this line
  GET /  // no blank line is needed after this line as well
  echo _  // no blank line is needed since function is always single-lined

No blank line is needed anywhere in the above code fragment since a following
HTTP statement or function statement can just as well signal the end of the previous
statement.

Peek starts with a default connection which assumes a locally running, unsecured
Elasticsearch cluster, i.e. ``http://localhost:9200``. This may not be the typical
cluster you want to connect in real use cases. Please run ``peek -h`` to see a list
of options to customise the start-up connection. You can also configure the
:ref:`default connection <default-connection>` with
``peekrc`` file to avoid having to specify them each time.


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

Note that API keys and tokens are treated differently. They are considered to be
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

Functions
---------

Builtin functions
^^^^^^^^^^^^^^^^^
Besides HTTP calls to Elasticsearch cluster. Peek also ships with a collection
of builtin functions for various things.
The single most useful one is likely the ``connect`` function. It takes an array
of options and creates a new connection to a cluster:

.. code-block:: javascript

  connect hosts='host1.example.com:9200,host2.example.com:9200' username='elastic' use_ssl=true

Note that quotes are required for string values. This is because Peek's CLI actually runs a
mini language (more on this later). The ``hosts`` option takes a comma separate list of
``host:port`` values. These connection options are handed directly to the
`Python Elasticsearch client <https://github.com/elastic/elasticsearch-py>`_, where
HTTP connection pooling, retry and so on are handled.

Another useful function is ``run``, which runs an external Peek script file:

.. code-block:: javascript

  run 'my-script.es'  // quotes are necessary

Any valid statements in the interactive mode can be put into a script for future references.


Type ``help`` to see the list of builtin functions. Use ``help FUNCTION_NAME`` to check
a bit more details on the specified function.

External functions
^^^^^^^^^^^^^^^^^^
Functions are simple Python callables. They can be defined in external files, loaded by Peek
and become available. Following is a simple external function that just print "hello world":

.. code-block:: python

  def hello_world_func(app):
      return 'hello world'

  EXPORTS = { 'hello': hello_world_func }

To load the extension, just specify it in the ``peekrc`` file like:

.. code-block:: ini

  extension_path = /path/to/external/extension/file/or/directory

Note the external function must accept at least one argument, which is the ``PeekApp``
instance. More sophisticated interactions are made possible with it:

.. code-block:: python

  class HealthFunc:
      def __call__(self, app, **options)
          import json
          conn = options.get('conn', None)
          app.process_input(f'GET /_cluster/health conn={json.dumps(conn)}')

      @property
      def options(self):
          return { 'conn': None }

      @property
      def description(self):
          return 'Health check for the Elasticsearch cluster'

The ``options`` and ``description` properties are optional. If provided, they will
be used to populate auto-completion and help message.
