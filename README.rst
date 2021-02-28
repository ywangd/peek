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

Please note the project requires Python 3.6+. It is recommended to install from PyPI with:

.. code-block:: bash

  pip install es-peek

The tool is now available as the ``peek`` command. Peek will ask permission to access system keyring
for storing credentials.
This can be disabled  temporarily by invoking the command as ``peek -e use_keyring=False``
or permanently by setting ``use_keyring = False`` in `peekrc <peek/peekrc>`_ file

Besides HTTP calls to Elasticsearch clusters, type ``help`` to see a list of builtin functions.
To **enable auto-completions** for APIs, run the ``_download_api_specs`` builtin function
(note the leading underscore) to download API spec files from the
`Kibana project <https://github.com/elastic/kibana>`_.

Alternatively, peek can also be installed from source with:

.. code-block:: bash

    python setup.py install

Features
--------

Peek supports most editing features offered by
`Kibana Console <https://www.elastic.co/guide/en/kibana/current/console-kibana.html>`_,
e.g. auto-completion, syntax highlighting, auto-formatting, auto-indent,
par-editing, triple-quotes, etc. It also offers following additional features:

* Lightweight CLI tool
* Multiplex a single terminal session to multiple Elasticsearch clusters or multiple connections to a single cluster
* Flexible usages of quotes, comma, comments for the JSON payload, case-insensitive http method names
* Multiple authentication schemes, including UserPass, API key, Token, SAML, OIDC, Kerberos, PKI
* Support run-as, x-opaque-id and arbitrary request headers
* Load JSON payload from external files
* Run file input in batch mode
* Readline editing features, e.g. ``Ctrl-_`` for undo, ``Ctrl-r`` for reverse search, etc.
* History management
* Capture terminal input and output into file
* Connect to `Elastic Cloud <https://cloud.elastic.co/>`_ with Cloud ID
* Shell out for system commands
* Minimal scripting support
* Extensible via external scripts

Sample Usages
-------------

Assuming a locally running Elasticsearch cluster, start a Peek session with:

.. code-block:: bash

  peek --hosts localhost:9200 --username elastic

The following sample is a quick guide on Peek usages:

.. code-block:: javascript

  // NOTE a blank line is needed to trigger API execution, or type "ESC + Enter" to execute regardlessly
  // Exit the interactive session any time by pressing Ctrl-d or type exit
  GET /_cluster/health  // comment is allowed almost anywhere

  // Index a single document
  POST /my-index/_doc
  {'foo': "bar"}  // both single and double quotes are acceptable

  // Bulk indexing
  // Press <F3> to switch between pretty and compact formatting for the JSON payload
  PUT _bulk
  {"index":{"_index":"test","_id":"1"}}
  {"value":"1","category":"click"}
  {"index":{"_index":"test","_id":"2"}}
  {"value":"2","category":"click"}

  // Auto encoding for date math expression
  // The following is encoded automatically into "PUT /%3Cmy-index-%7Bnow%2Fd%7D%3E" on the background
  PUT /<my-index-{now/d}>

  // Shell out to download the EQL threat hunting demo file
  !curl -o normalized-T1117-AtomicRed-regsvr32.json https://raw.githubusercontent.com/elastic/elasticsearch/master/docs/src/test/resources/normalized-T1117-AtomicRed-regsvr32.json

  // Bulk indexing the above downloaded file
  POST my-index-000001/_bulk
  @normalized-T1117-AtomicRed-regsvr32.json

  // Execute an EQL query (triple quotes can be either ''' or """)
  GET /my-index-000001/_eql/search?filter_path=-hits.events
  {
    "query": """
      any where process.name == "regsvr32.exe"
    """,
    "size": 200
  }

  // Create an API key
  PUT _security/api_key
  {
    "name": "key-1",  // extra comma is OK, and this comment is ok as well
  }

  // Connect using the above generated API key
  // The dot notation is used to index into JSON object and array
  connect api_key=_.'id' + ":" + _.'api_key' hosts='localhost:9200'  // Quotes are necessary for strings

  // Connect to Elastic Cloud with Cloud ID
  connect cloud_id='YOUR_CLOUD_ID' username='elastic'

  // Issue a call to the cloud cluster
  get /  // HTTP method is case-insensitive
  get / conn=0  // send the request to the first connection (zero-based index) with the conn option

  // Check configuration location and values
  config

  // List available connections
  connection
  connection @info  // check details
  connection rename='my-cloud-cluster'  // give a friendly name to the current connection
  connection 0  // switch to the first connection
  connection remove=0  // remove the first connection
  connection 'my-cloud-cluster'  // switch to the cloud cluster connection

  // Save the connections we have so far. Session is also auto-saved on exit.
  session @save  // it can be loaded later with "session @load"

  // Session auto-load on start up can be enabled by set "auto_load_session = True" in peekrc file.
  // This helps preserving connections across restart.

  // Builtin help
  help  // list available functions
  help session  // a bit more detailed info about the "session" builtin function

  // Capture the terminal I/O
  capture @start
  capture  // show capture status

  // Run-AS and other headers
  GET _security/_authenticate runas='foo' xoid='my-x-opaque-id' headers={'some-other-header': 'blah'}

  // Show only the first role from previous response
  echo _."roles".0

  // If the cluster has SAML integration configured, authenticate with saml
  // Note this opens a web browser to perform the front-channel flow
  saml_authenticate

  // Load and run an external script
  run 'my-setup.es'

  // Stop the capture
  capture @stop

  // Minimal scripting for populating an index
  let tags = range(0, 100)
  for i in tags {
    PUT ("my-index/_doc/" + i)
    { 'tag': i, "value": i * i }
  }

  // Or with bulk index
  for i in range(1, 100) {  // first prepare the payload file
    echo {"index":{"_index":"test","_id":"" + i}} file='payload.json'
    echo {"value":i,"category":"click"} file='payload.json'
  }
  // Now bulk indexing with the above generated file
  PUT _bulk
  @payload.json

The tool can also run in batch mode. Assuming above commands are saved in a file called ``script.es``,
it can be executed as:

.. code-block:: bash

  # Positional argument
  peek script.es

  # Pipe
  cat script.es | peek

  # Or with heredoc
  peek << EOF
  GET /_cluster/health
  // etc
  EOF

External scripts can used to provide extra functions. They are simple Python scripts that define
and expose callabes under a variable named ``EXPORTS``. Please refer `natives.py <peek/natives.py>`_
for examples.

Please also read `Usages <docs/usage.rst>`_ for more details.

Credits
-------
`Pgcli <https://github.com/dbcli/pgcli>`_ has been a great reference of learning how to use
`prompt-toolkit <https://github.com/prompt-toolkit/python-prompt-toolkit>`_, which is a critical
dependency of this project.
